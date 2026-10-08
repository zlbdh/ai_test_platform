# -*- coding: utf-8 -*-
"""
Shared logging configuration: trace_id request tracing and structured formatting
All modules inherit this configuration through logging.getLogger(__name__).
"""
import logging
import uuid
from contextvars import ContextVar

# ── trace_id context ─────────────────────────────────────────
# Middleware assigns a unique trace_id that is available throughout each request
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    """Get the current request's trace_id for logs or response headers"""
    return trace_id_var.get()


def new_trace_id() -> str:
    """Generate, set, and return a new trace_id"""
    tid = uuid.uuid4().hex[:12]
    trace_id_var.set(tid)
    return tid


# ── Custom Formatter that injects trace_id──────────────────────
class TraceFormatter(logging.Formatter):
    """Inject trace_id into each log record automatically"""

    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = trace_id_var.get()
        return super().format(record)


# ── Initialization function; call once before application startup────────────────────
_initialized = False

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(trace_id)s | %(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure the project's root logger with a consistent format.
    Idempotent: repeated calls do not add duplicate handlers.
    """
    global _initialized
    if _initialized:
        return

    formatter = TraceFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to prevent duplicate output from basicConfig's default handler
    root.handlers.clear()
    root.addHandler(console_handler)

    # Reduce third-party logging noise
    for noisy in ["httpx", "httpcore", "urllib3", "watchfiles", "uvicorn.access"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _initialized = True
