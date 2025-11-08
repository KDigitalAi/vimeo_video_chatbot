"""
Cache utilities for memory management.
"""
import time
from typing import Optional, Dict, Any
from weakref import WeakValueDictionary

class AdvancedCache:
    """Cache with LRU eviction for memory management."""
    
    def __init__(self, max_size: int = 100):
        self._cache = WeakValueDictionary()
        self._max_size = max_size
        self._access_count = {}
        self._access_time = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Cache retrieval with LRU eviction."""
        if key in self._cache:
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._access_time[key] = time.time()
            return self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Cache storage with automatic eviction."""
        if len(self._cache) >= self._max_size:
            self._evict_lru()
        
        self._cache[key] = value
        self._access_count[key] = 1
        self._access_time[key] = time.time()
    
    def _evict_lru(self) -> None:
        """LRU eviction."""
        if not self._cache:
            return
        
        lru_key = min(self._access_time.keys(), key=lambda k: self._access_time[k])
        del self._cache[lru_key]
        del self._access_count[lru_key]
        del self._access_time[lru_key]
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._access_count.clear()
        self._access_time.clear()

