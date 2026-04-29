# -*- coding: utf-8 -*-
"""
统一日志配置 — trace_id 链路追踪 + 结构化格式
所有模块通过 logging.getLogger(__name__) 自动继承此配置。
"""
import logging
import uuid
from contextvars import ContextVar

# ── trace_id 上下文 ─────────────────────────────────────────
# 每个请求在中间件中设置唯一 trace_id，整个请求链路均可访问
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    """获取当前请求的 trace_id（供日志或响应头使用）"""
    return trace_id_var.get()


def new_trace_id() -> str:
    """生成并设置新的 trace_id，返回该值"""
    tid = uuid.uuid4().hex[:12]
    trace_id_var.set(tid)
    return tid


# ── 自定义 Formatter（注入 trace_id）──────────────────────
class TraceFormatter(logging.Formatter):
    """自动将 trace_id 注入每条日志"""

    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = trace_id_var.get()
        return super().format(record)


# ── 初始化函数（应在 app 启动前调用一次）────────────────────
_initialized = False

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(trace_id)s | %(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """
    配置项目根 logger，统一格式。
    幂等：多次调用不会重复添加 handler。
    """
    global _initialized
    if _initialized:
        return

    formatter = TraceFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # 移除已有的 handler（避免 basicConfig 的默认 handler 导致重复输出）
    root.handlers.clear()
    root.addHandler(console_handler)

    # 降低第三方库噪音
    for noisy in ["httpx", "httpcore", "urllib3", "watchfiles", "uvicorn.access"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _initialized = True
