"""
Logging utilities and memory management.
"""
import logging
import gc
import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

# Initialize logger first to prevent import errors
logger = logging.getLogger("vimeo_chatbot")

# Optional import for memory monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available, memory monitoring disabled")

# Singleton logger to avoid multiple handlers
_logger_instance = None

def get_logger():
    """Get singleton logger instance to reduce memory usage.

    On serverless (read-only filesystem), avoid creating files/directories and
    log to stdout instead. If a writable temp directory exists, prefer /tmp.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = logging.getLogger("vimeo_chatbot")
        _logger_instance.setLevel(logging.INFO)

        if not _logger_instance.handlers:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

            # Detect read-only envs like Vercel and prefer stdout logging
            vercel_env = os.environ.get("VERCEL") or os.environ.get("NOW_BUILDER")

            # Attempt to use /tmp if available and not readonly
            tmp_dir = Path("/tmp/backend_logs")
            use_file = False
            try:
                if not vercel_env:
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    test_path = tmp_dir / ".writable"
                    with open(test_path, "w") as f:
                        f.write("ok")
                    test_path.unlink(missing_ok=True)
                    use_file = True
            except Exception:
                use_file = False

            if use_file:
                fh = logging.FileHandler(tmp_dir / "chatbot.log")
                fh.setFormatter(formatter)
                _logger_instance.addHandler(fh)
            else:
                sh = logging.StreamHandler()
                sh.setFormatter(formatter)
                _logger_instance.addHandler(sh)

    return _logger_instance

# Use singleton logger - wrap in try/except to prevent import failures
try:
    logger = get_logger()
except Exception:
    # Fallback to basic logger if get_logger() fails (e.g., filesystem issues)
    logger = logging.getLogger("vimeo_chatbot")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)

def safe_get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default

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
    logger.info(f"Memory usage after {operation}: {memory_mb:.2f} MB")

def cleanup_memory():
    """Force garbage collection to free up memory."""
    collected = gc.collect()
    logger.info(f"Garbage collection freed {collected} objects")
    return collected

def check_memory_threshold(threshold_mb: float = 6000) -> bool:
    """Check if memory usage is below threshold (default 6GB for 8GB system)."""
    memory_mb = get_memory_usage()
    if memory_mb > threshold_mb:
        logger.warning(f"Memory usage {memory_mb:.2f} MB exceeds threshold {threshold_mb} MB")
        cleanup_memory()
        return False
    return True
