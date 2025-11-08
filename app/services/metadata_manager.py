"""
Metadata management for video metadata caching.
"""
import json
import gc
from pathlib import Path
import os
from functools import lru_cache
from typing import Dict, Optional
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold

# Prefer writable temp directory on serverless environments
_DEFAULT_META_DIR = os.environ.get("METADATA_DIR", "/tmp/backend_metadata")
META_DIR = Path(_DEFAULT_META_DIR)
try:
    META_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # Fall back to stdout-only logging if directory cannot be created
    # and avoid raising during import on read-only filesystems
    pass

# File cache to reduce I/O operations with size limit
_file_cache = {}
_MAX_CACHE_SIZE = 100  # Limit cache to 100 entries

def save_video_metadata(video_id: str, metadata: Dict) -> str:
    """
    Save video metadata with caching and memory optimization.
    Optimized for reduced I/O operations.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before saving metadata")
        cleanup_memory()
    
    try:
        p = META_DIR / f"{video_id}.json"
        
        # Truncate metadata if too large to prevent memory issues
        max_metadata_size = 50000  # 50KB limit
        if len(str(metadata)) > max_metadata_size:
            logger.warning(f"Metadata for video {video_id} is too large, truncating")
            # Keep only essential fields
            essential_fields = ['name', 'description', 'duration', 'created_time', 'modified_time']
            metadata = {k: v for k, v in metadata.items() if k in essential_fields}
        
        try:
            with p.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as write_err:
            logger.warning(f"Metadata directory not writable; skipping save for {video_id}: {write_err}")
            return str(p)
        
        # Update cache with size limit
        if len(_file_cache) >= _MAX_CACHE_SIZE:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(_file_cache))
            del _file_cache[oldest_key]
        _file_cache[video_id] = metadata
        
        logger.info("Saved metadata for video %s", video_id)
        log_memory_usage(f"metadata save for {video_id}")
        return str(p)
        
    except Exception as e:
        logger.error(f"Failed to save metadata for video {video_id}: {e}")
        cleanup_memory()
        raise

@lru_cache(maxsize=64)
def load_video_metadata(video_id: str) -> Optional[Dict]:
    """
    Load video metadata with caching to reduce I/O operations.
    Optimized for time complexity O(1) with cache hits.
    """
    # Check cache first
    if video_id in _file_cache:
        return _file_cache[video_id]
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before loading metadata")
        cleanup_memory()
    
    try:
        p = META_DIR / f"{video_id}.json"
        if not p.exists():
            return None
        
        # Load metadata
        with p.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Update cache with size limit
        if len(_file_cache) >= _MAX_CACHE_SIZE:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(_file_cache))
            del _file_cache[oldest_key]
        _file_cache[video_id] = metadata
        
        log_memory_usage(f"metadata load for {video_id}")
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to load metadata for video {video_id}: {e}")
        cleanup_memory()
        return None

def clear_metadata_cache():
    """Clear the metadata cache to free memory."""
    global _file_cache
    _file_cache.clear()
    gc.collect()
    logger.info("Metadata cache cleared")
