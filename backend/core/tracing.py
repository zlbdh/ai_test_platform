# -*- coding: utf-8 -*-
"""
Tracing — LLM 调用链路追踪

轻量级实现，不强依赖外部 Langfuse 服务：
- TraceSpan 记录每次 LLM 调用的 token 用量、延迟、成本
- 基于 SQLite 持久化（复用 data/ 目录）
- 提供装饰器 @traced 自动记录 LLM 调用
- 支持获取成本汇总、性能瓶颈分析
"""

import functools
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────


@dataclass
class TraceSpan:
    """一次 LLM 调用的追踪记录"""
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    trace_id: str = ""            # 所属 trace（一个 Commander 任务 = 一个 trace）
    agent_name: str = ""          # 调用方 Agent
    action: str = ""              # 调用动作，如 "plan_test", "select_strategy"
    model: str = ""               # 模型名称
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0      # 耗时（毫秒）
    cost_usd: float = 0.0        # 估算成本（美元）
    status: str = "ok"            # ok / error
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ── 成本估算 ─────────────────────────────────────────────────────────────────

# 近似的每百万 token 价格（美元）
_COST_PER_M_TOKENS = {
    "claude-haiku-4-5-20251001": {"input": 0.9, "output": 4.5},
    "claude-haiku": {"input": 0.9, "output": 4.5},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "gemini-pro": {"input": 0.5, "output": 1.5},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算 LLM 调用成本"""
    for key, prices in _COST_PER_M_TOKENS.items():
        if key in model.lower():
            return (
                input_tokens * prices["input"] / 1_000_000
                + output_tokens * prices["output"] / 1_000_000
            )
    # 默认回落到当前资源包模型的价格估算
    return (input_tokens * 0.9 + output_tokens * 4.5) / 1_000_000


# ── Tracer 核心 ──────────────────────────────────────────────────────────────


class Tracer:
    """
    LLM 调用链路追踪器

    使用方式：
        tracer = get_tracer()

        # 方式 1：上下文管理器
        with tracer.span("commander", "plan_test") as s:
            result = llm.invoke(prompt)
            s.input_tokens = result.usage.prompt_tokens
            s.output_tokens = result.usage.completion_tokens

        # 方式 2：直接记录
        tracer.record(TraceSpan(agent_name="planner", action="generate_plan", ...))
    """

    def __init__(self):
        self._db_path = self._get_db_path()
        self._init_db()
        self._current_trace_id: Optional[str] = None
        logger.info(f"[Tracer] 初始化完成，DB: {self._db_path}")
        
        # LangSmith 集成：当环境变量启用时自动附加 LangChain 回调
        self._langsmith_handler = None
        try:
            from core.config import Config
            if Config.LANGCHAIN_TRACING_V2 and Config.LANGCHAIN_API_KEY:
                import os
                os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
                os.environ.setdefault("LANGCHAIN_API_KEY", Config.LANGCHAIN_API_KEY)
                os.environ.setdefault("LANGCHAIN_PROJECT", Config.LANGCHAIN_PROJECT)
                try:
                    from langchain_core.tracers import LangChainTracer
                    self._langsmith_handler = LangChainTracer(project_name=Config.LANGCHAIN_PROJECT)
                    logger.info(f"[Tracer] ✅ LangSmith 集成已启用，项目: {Config.LANGCHAIN_PROJECT}")
                except ImportError:
                    logger.info("[Tracer] langchain_core 未安装，LangSmith 回调跳过")
        except Exception as e:
            logger.debug(f"[Tracer] LangSmith 初始化跳过: {e}")

    def _get_db_path(self) -> str:
        """获取 SQLite 数据库路径"""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base, "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "tracing.db")

    def _init_db(self) -> None:
        """初始化表结构"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trace_spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT,
                    agent_name TEXT,
                    action TEXT,
                    model TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    duration_ms REAL DEFAULT 0,
                    cost_usd REAL DEFAULT 0,
                    status TEXT DEFAULT 'ok',
                    error_message TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_id ON trace_spans(trace_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_name ON trace_spans(agent_name)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[Tracer] DB 初始化失败: {e}")

    # ── Trace 生命周期 ────────────────────────────────────────────────────

    def start_trace(self, trace_id: Optional[str] = None) -> str:
        """开始一个新的 trace（对应一个 Commander 任务）"""
        self._current_trace_id = trace_id or str(uuid.uuid4())[:12]
        return self._current_trace_id

    def end_trace(self) -> Optional[str]:
        """结束当前 trace"""
        tid = self._current_trace_id
        self._current_trace_id = None
        return tid

    @property
    def current_trace_id(self) -> Optional[str]:
        return self._current_trace_id

    # ── 记录 Span ─────────────────────────────────────────────────────────

    def get_langsmith_callbacks(self) -> list:
        """获取 LangSmith 回调列表，供 LLM 调用时注入"""
        if self._langsmith_handler:
            return [self._langsmith_handler]
        return []

    @contextmanager
    def span(self, agent_name: str, action: str, model: str = ""):
        """
        上下文管理器：自动记录 LLM 调用的耗时。

        Examples:
            with tracer.span("planner", "generate_plan", "deepseek-chat") as s:
                result = llm.invoke(prompt)
                s.input_tokens = 150
                s.output_tokens = 300
        """
        s = TraceSpan(
            trace_id=self._current_trace_id or "",
            agent_name=agent_name,
            action=action,
            model=model,
        )
        start_time = time.time()

        try:
            yield s
        except Exception as e:
            s.status = "error"
            s.error_message = str(e)
            raise
        finally:
            s.duration_ms = (time.time() - start_time) * 1000
            s.total_tokens = s.input_tokens + s.output_tokens
            s.cost_usd = _estimate_cost(s.model, s.input_tokens, s.output_tokens)
            self.record(s)

    def record(self, span: TraceSpan) -> None:
        """持久化一条 Span 记录"""
        try:
            import json
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO trace_spans
                   (span_id, trace_id, agent_name, action, model,
                    input_tokens, output_tokens, total_tokens,
                    duration_ms, cost_usd, status, error_message,
                    metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span.span_id, span.trace_id, span.agent_name, span.action,
                    span.model, span.input_tokens, span.output_tokens,
                    span.total_tokens, span.duration_ms, span.cost_usd,
                    span.status, span.error_message,
                    json.dumps(span.metadata, ensure_ascii=False),
                    span.timestamp,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[Tracer] 写入失败: {e}")

    # ── 查询与统计 ────────────────────────────────────────────────────────

    def get_trace_spans(self, trace_id: str) -> List[Dict]:
        """获取指定 trace 的所有 span"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trace_spans WHERE trace_id = ? ORDER BY timestamp",
                (trace_id,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[Tracer] 查询失败: {e}")
            return []

    def get_trace_summary(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 trace 成本摘要。

        如果不指定 trace_id，返回全局统计。
        """
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            where = "WHERE trace_id = ?" if trace_id else ""
            params = (trace_id,) if trace_id else ()

            row = conn.execute(f"""
                SELECT
                    COUNT(*) as total_calls,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                    COALESCE(MAX(duration_ms), 0) as max_duration_ms,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
                FROM trace_spans {where}
            """, params).fetchone()

            # 按 Agent 分组统计
            agent_rows = conn.execute(f"""
                SELECT
                    agent_name,
                    COUNT(*) as calls,
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COALESCE(SUM(cost_usd), 0) as cost
                FROM trace_spans {where}
                GROUP BY agent_name
                ORDER BY cost DESC
            """, params).fetchall()

            conn.close()

            return {
                "trace_id": trace_id,
                "total_calls": row["total_calls"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": round(row["total_cost_usd"], 6),
                "avg_duration_ms": round(row["avg_duration_ms"], 1),
                "max_duration_ms": round(row["max_duration_ms"], 1),
                "error_count": row["error_count"],
                "by_agent": [
                    {
                        "agent": r["agent_name"],
                        "calls": r["calls"],
                        "tokens": r["tokens"],
                        "cost_usd": round(r["cost"], 6),
                    }
                    for r in agent_rows
                ],
            }
        except Exception as e:
            logger.error(f"[Tracer] 统计失败: {e}")
            return {"error": str(e)}

    def get_recent_spans(self, limit: int = 20) -> List[Dict]:
        """获取最近的 span 记录"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trace_spans ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[Tracer] 查询失败: {e}")
            return []


# ── 单例 ─────────────────────────────────────────────────────────────────────

_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """获取 Tracer 单例"""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
