"""
Shared runtime safety helpers for settings, logging, and memory guards.
"""
from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from typing import Any


def get_logger_safe(name: str | None = None):
    """Return the shared app logger, or a basic fallback logger."""
    try:
        from app.utils.logger import logger

        return logger
    except Exception:
        fallback_logger = logging.getLogger(name or __name__)
        if not fallback_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            fallback_logger.addHandler(handler)
        fallback_logger.setLevel(logging.INFO)
        return fallback_logger


def get_settings_safe() -> Any:
    """Return app settings, or a minimal env-backed fallback object."""
    try:
        from app.config.settings import settings

        return settings
    except Exception as exc:
        get_logger_safe(__name__).error("Failed to import settings safely: %s", exc)
        return SimpleNamespace(
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            EMBEDDING_MODEL=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            EMBEDDING_DIMENSIONS=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
            SUPABASE_URL=os.getenv("SUPABASE_URL", ""),
            SUPABASE_SERVICE_KEY=os.getenv("SUPABASE_SERVICE_KEY", ""),
            SUPABASE_TABLE=os.getenv("SUPABASE_TABLE", "pdf_embeddings"),
        )


def memory_guard(logger, operation: str, *, threshold_mb: float = 6000) -> bool:
    """
    Run the standard memory threshold/cleanup guard.
    Returns True when memory is below threshold, False otherwise.
    """
    try:
        from app.utils.logger import check_memory_threshold, cleanup_memory

        if not check_memory_threshold(threshold_mb):
            logger.warning("Memory usage high before %s", operation)
            cleanup_memory()
            return False
        return True
    except Exception:
        return True
