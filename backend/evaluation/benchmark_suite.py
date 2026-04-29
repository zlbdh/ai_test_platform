# -*- coding: utf-8 -*-
"""
Benchmark Suite — 标准化基准测试套件

提供可重复的标准化测试场景，用于评估Agent在不同场景下的表现。
支持自定义场景、模型对比和历史趋势。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import json
import os
import time
import sqlite3
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkScenario:
    """基准测试场景"""
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"   # general, navigation, form, search, auth, complex
    goal: str = ""              # 自然语言任务描述
    target_url: str = ""        # 目标 URL
    expected_steps: int = 0     # 预期步骤数
    timeout_seconds: int = 120
    difficulty: str = "medium"  # easy, medium, hard
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "goal": self.goal,
            "target_url": self.target_url,
            "expected_steps": self.expected_steps,
            "timeout_seconds": self.timeout_seconds,
            "difficulty": self.difficulty,
            "tags": self.tags,
        }


# ── 预定义基准场景 ──────────────────────────────────────────────────────────

BUILTIN_SCENARIOS: List[BenchmarkScenario] = [
    BenchmarkScenario(
        id="search_baidu",
        name="百度搜索",
        description="在百度搜索引擎中搜索关键词并验证结果",
        category="search",
        goal="打开百度，搜索 'AI测试'，验证搜索结果页面显示了相关内容",
        target_url="https://www.baidu.com",
        expected_steps=5,
        difficulty="easy",
        tags=["search", "input", "navigation"],
    ),
    BenchmarkScenario(
        id="search_bing",
        name="Bing搜索",
        description="在Bing搜索引擎中搜索并验证",
        category="search",
        goal="打开Bing，搜索 'selenium automation'，验证搜索结果存在",
        target_url="https://www.bing.com",
        expected_steps=5,
        difficulty="easy",
        tags=["search", "input"],
    ),
    BenchmarkScenario(
        id="github_navigation",
        name="GitHub导航",
        description="在GitHub上导航到指定仓库并检查信息",
        category="navigation",
        goal="打开 GitHub，搜索 'playwright'，点击第一个搜索结果，验证页面显示了仓库信息",
        target_url="https://github.com",
        expected_steps=8,
        difficulty="medium",
        tags=["navigation", "search", "verification"],
    ),
    BenchmarkScenario(
        id="form_fill_basic",
        name="基础表单填写",
        description="在demo表单中填写信息",
        category="form",
        goal="打开 https://demoqa.com/text-box，填写 Full Name 为 'AI Tester'，Email 为 'ai@test.com'，然后点击 Submit 按钮",
        target_url="https://demoqa.com/text-box",
        expected_steps=6,
        difficulty="easy",
        tags=["form", "input", "click"],
    ),
    BenchmarkScenario(
        id="multi_step_nav",
        name="多步导航",
        description="在网站中执行多步复合导航",
        category="complex",
        goal="打开 https://www.wikipedia.org，切换到中文版，搜索 '人工智能'，点击第一段中任意一个链接",
        target_url="https://www.wikipedia.org",
        expected_steps=10,
        difficulty="hard",
        tags=["navigation", "multi_step", "complex"],
    ),
    BenchmarkScenario(
        id="dropdown_select",
        name="下拉菜单选择",
        description="在页面上操作下拉菜单",
        category="form",
        goal="打开 https://demoqa.com/select-menu，选择 Old Style Select Menu 中的 'Blue' 选项",
        target_url="https://demoqa.com/select-menu",
        expected_steps=5,
        difficulty="medium",
        tags=["form", "select", "dropdown"],
    ),
    BenchmarkScenario(
        id="dynamic_element",
        name="动态元素等待",
        description="等待并操作动态加载的元素",
        category="complex",
        goal="打开 https://demoqa.com/dynamic-properties，等待 'Visible After 5 Seconds' 按钮出现后点击它",
        target_url="https://demoqa.com/dynamic-properties",
        expected_steps=4,
        difficulty="medium",
        tags=["dynamic", "wait", "click"],
    ),
    BenchmarkScenario(
        id="checkbox_toggle",
        name="复选框操作",
        description="展开树形结构并切换复选框",
        category="form",
        goal="打开 https://demoqa.com/checkbox，展开 Home 节点，然后勾选 Desktop 复选框",
        target_url="https://demoqa.com/checkbox",
        expected_steps=5,
        difficulty="medium",
        tags=["form", "checkbox", "tree"],
    ),
]


@dataclass
class BenchmarkRunResult:
    """基准测试运行结果"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    scenario_id: str = ""
    model: str = ""
    provider: str = ""
    success: bool = False
    overall_score: float = 0.0
    metric_scores: Dict[str, float] = field(default_factory=dict)
    judge_scores: Dict[str, float] = field(default_factory=dict)
    duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    step_count: int = 0
    healing_count: int = 0
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "model": self.model,
            "provider": self.provider,
            "success": self.success,
            "overall_score": round(self.overall_score, 4),
            "metric_scores": {k: round(v, 4) for k, v in self.metric_scores.items()},
            "judge_scores": {k: round(v, 2) for k, v in self.judge_scores.items()},
            "duration_ms": round(self.duration_ms, 1),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "step_count": self.step_count,
            "healing_count": self.healing_count,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }


class BenchmarkSuite:
    """基准测试套件管理"""

    def __init__(self):
        self.scenarios: Dict[str, BenchmarkScenario] = {}
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "evaluation.db"
        )
        # 加载内置场景
        for s in BUILTIN_SCENARIOS:
            self.scenarios[s.id] = s
        self._init_db()

    def _init_db(self):
        """初始化评估数据库"""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT,
                    goal TEXT,
                    model TEXT,
                    provider TEXT,
                    success INTEGER,
                    overall_score REAL,
                    metric_scores TEXT,
                    judge_scores TEXT,
                    duration_ms REAL,
                    total_tokens INTEGER,
                    total_cost_usd REAL,
                    step_count INTEGER,
                    healing_count INTEGER,
                    error_message TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_scenarios (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    created_at REAL
                )
            """)

    def list_scenarios(self, category: str = "") -> List[Dict]:
        """列出所有可用场景"""
        scenarios = list(self.scenarios.values())
        # 加载自定义场景
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("SELECT data FROM custom_scenarios").fetchall()
                for row in rows:
                    data = json.loads(row[0])
                    s = BenchmarkScenario(**data)
                    if s.id not in self.scenarios:
                        scenarios.append(s)
        except Exception:
            pass

        if category:
            scenarios = [s for s in scenarios if s.category == category]

        return [s.to_dict() for s in scenarios]

    def get_scenario(self, scenario_id: str) -> Optional[BenchmarkScenario]:
        """获取单个场景"""
        return self.scenarios.get(scenario_id)

    def add_custom_scenario(self, scenario: BenchmarkScenario):
        """添加自定义场景"""
        if not scenario.id:
            scenario.id = f"custom_{str(uuid.uuid4())[:8]}"
        self.scenarios[scenario.id] = scenario
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO custom_scenarios (id, data, created_at) VALUES (?, ?, ?)",
                (scenario.id, json.dumps(scenario.to_dict(), ensure_ascii=False), time.time()),
            )

    def save_run_result(self, result: BenchmarkRunResult, goal: str = ""):
        """持久化运行结果"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO evaluation_runs
                (run_id, scenario_id, goal, model, provider, success, overall_score,
                 metric_scores, judge_scores, duration_ms, total_tokens, total_cost_usd,
                 step_count, healing_count, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.run_id, result.scenario_id, goal, result.model, result.provider,
                int(result.success), result.overall_score,
                json.dumps(result.metric_scores), json.dumps(result.judge_scores),
                result.duration_ms, result.total_tokens, result.total_cost_usd,
                result.step_count, result.healing_count, result.error_message,
                result.timestamp,
            ))

    def get_results(self, scenario_id: str = "", limit: int = 50) -> List[Dict]:
        """获取历史评估结果"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                if scenario_id:
                    rows = conn.execute(
                        "SELECT * FROM evaluation_runs WHERE scenario_id = ? ORDER BY timestamp DESC LIMIT ?",
                        (scenario_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                results = []
                for r in rows:
                    d = dict(r)
                    d["metric_scores"] = json.loads(d.get("metric_scores", "{}"))
                    d["judge_scores"] = json.loads(d.get("judge_scores", "{}"))
                    results.append(d)
                return results
        except Exception as e:
            logger.error(f"获取评估结果失败: {e}")
            return []

    def compare_models(self, scenario_id: str = "") -> Dict[str, Any]:
        """对比不同模型在相同场景下的表现"""
        results = self.get_results(scenario_id=scenario_id, limit=200)
        if not results:
            return {"models": {}, "message": "暂无评估数据"}

        model_stats = {}
        for r in results:
            model = r.get("model", "unknown")
            if model not in model_stats:
                model_stats[model] = {
                    "runs": 0,
                    "successes": 0,
                    "total_score": 0.0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "total_duration": 0.0,
                }
            stats = model_stats[model]
            stats["runs"] += 1
            stats["successes"] += int(r.get("success", 0))
            stats["total_score"] += r.get("overall_score", 0)
            stats["total_tokens"] += r.get("total_tokens", 0)
            stats["total_cost"] += r.get("total_cost_usd", 0)
            stats["total_duration"] += r.get("duration_ms", 0)

        comparison = {}
        for model, stats in model_stats.items():
            runs = stats["runs"] or 1
            comparison[model] = {
                "runs": stats["runs"],
                "success_rate": round(stats["successes"] / runs, 3),
                "avg_score": round(stats["total_score"] / runs, 4),
                "avg_tokens": round(stats["total_tokens"] / runs),
                "avg_cost_usd": round(stats["total_cost"] / runs, 4),
                "avg_duration_ms": round(stats["total_duration"] / runs, 1),
            }

        return {"models": comparison}
