"""Logging utilities and memory management."""
from __future__ import annotations

import gc
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.core.request_context import get_request_context

logger = logging.getLogger("pdf_chatbot")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

_logger_initialized = False


class JsonLogFormatter(logging.Formatter):
    """Render logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": context.get("request_id"),
            "user_id": context.get("user_id"),
            "session_id": context.get("session_id"),
            "path": context.get("path"),
            "method": context.get("method"),
            "module": record.name,
            "extra": getattr(record, "extra_fields", {}),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StructuredLogger:
    """Thin logger wrapper that injects structured extra fields."""

    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    def _log(self, level: int, message: str, *args, exc_info=None, stack_info=False, **kwargs):
        kwargs.setdefault("component", self._logger.name)
        kwargs.setdefault("operation", "log")
        self._logger.log(
            level,
            message,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            extra={"extra_fields": kwargs or {}},
        )

    def debug(self, message: str, *args, **kwargs):
        self._log(logging.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._log(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._log(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._log(logging.ERROR, message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._log(logging.ERROR, message, *args, exc_info=True, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._log(logging.CRITICAL, message, *args, **kwargs)


def _build_handler() -> logging.Handler:
    """Build the configured log handler."""
    formatter = JsonLogFormatter()
    vercel_env = os.environ.get("VERCEL") or os.environ.get("NOW_BUILDER")
    tmp_dir = Path("/tmp/backend_logs")
    use_file = False
    try:
        if not vercel_env:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            test_path = tmp_dir / ".writable"
            with open(test_path, "w", encoding="utf-8") as handle:
                handle.write("ok")
            test_path.unlink(missing_ok=True)
            use_file = True
    except Exception:
        use_file = False

    handler: logging.Handler
    if use_file:
        handler = logging.FileHandler(tmp_dir / "chatbot.log")
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return handler


def _configure_root_logger() -> None:
    """Configure the shared root logger once."""
    global _logger_initialized
    if _logger_initialized:
        return

    root_logger = logging.getLogger("vimeo_chatbot")
    configured_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, configured_level, logging.INFO))
    if not root_logger.handlers:
        root_logger.addHandler(_build_handler())
    _logger_initialized = True


def get_logger(name: str | None = None) -> StructuredLogger:
    """Return a structured logger bound to the given module name."""
    _configure_root_logger()
    return StructuredLogger(logging.getLogger(name or "vimeo_chatbot"))


try:
    logger = get_logger()
except Exception:
    fallback_logger = logging.getLogger("pdf_chatbot")
    fallback_logger.setLevel(logging.INFO)
    if not fallback_logger.handlers:
        fallback_logger.addHandler(_build_handler())
    logger = StructuredLogger(fallback_logger)


def log_info(message: str, **kwargs) -> None:
    """Log a structured info message."""
    logger.info(message, **kwargs)


def log_error(message: str, **kwargs) -> None:
    """Log a structured error message."""
    logger.error(message, **kwargs)


def log_exception(message: str, exc: Exception, **kwargs) -> None:
    """Log a structured exception with traceback."""
    logger.exception(message, error_type=type(exc).__name__, **kwargs)


@lru_cache(maxsize=128)
def get_memory_usage():
    """Get current memory usage in MB."""
    if not PSUTIL_AVAILABLE:
        return 0.0

    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


def log_memory_usage(operation: str):
    """Log memory usage for a specific operation."""
    memory_mb = get_memory_usage()
    logger.info("Memory usage sampled", operation=operation, memory_mb=round(memory_mb, 2))


def cleanup_memory():
    """Force garbage collection to free up memory."""
    collected = gc.collect()
    logger.info("Garbage collection completed", objects_collected=collected)
    return collected


def check_memory_threshold(threshold_mb: float = 6000) -> bool:
    """Check if memory usage is below threshold (default 6GB for 8GB system)."""
    memory_mb = get_memory_usage()
    if memory_mb > threshold_mb:
        logger.warning(
            "Memory usage exceeds threshold",
            memory_mb=round(memory_mb, 2),
            threshold_mb=threshold_mb,
        )
        cleanup_memory()
        return False
    return True
