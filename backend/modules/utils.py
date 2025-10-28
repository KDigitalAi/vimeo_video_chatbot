# backend/modules/utils.py
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
    """Get singleton logger instance to reduce memory usage."""
    global _logger_instance
    if _logger_instance is None:
        LOG_DIR = Path("backend/logs")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        _logger_instance = logging.getLogger("vimeo_chatbot")
        _logger_instance.setLevel(logging.INFO)
        
        # Only add handler if not already present
        if not _logger_instance.handlers:
            fh = logging.FileHandler(LOG_DIR / "chatbot.log")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh.setFormatter(formatter)
            _logger_instance.addHandler(fh)
    
    return _logger_instance

# Use singleton logger
logger = get_logger()

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