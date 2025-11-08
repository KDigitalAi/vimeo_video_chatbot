"""
Vimeo API integration for video metadata and content.
"""
import requests
import gc
from functools import lru_cache
from typing import Dict, List, Optional
from app.config.settings import settings
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold

# Lazy import to reduce memory footprint
def _get_whisper_transcriber():
    from app.services.whisper_transcriber import transcribe_vimeo_audio
    return transcribe_vimeo_audio

# Validate Vimeo access token early
if not settings.VIMEO_ACCESS_TOKEN or settings.VIMEO_ACCESS_TOKEN.startswith("your_"):
    logger.warning("VIMEO_ACCESS_TOKEN is not properly configured. Vimeo API calls will fail.")
    HEADERS = {}
else:
    HEADERS = {"Authorization": f"Bearer {settings.VIMEO_ACCESS_TOKEN}"}

_session = None

def get_session():
    """Get or create a requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        # Configure session for optimal performance
        _session.headers.update(HEADERS)
        
        # Optimized connection pooling settings
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,  # Increased for better concurrency
            pool_maxsize=50,      # Increased for better throughput
            max_retries=3,        # Retry failed requests
            pool_block=False     # Non-blocking pool
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
        
        # Set optimal timeouts
        _session.timeout = (5, 30)  # (connect, read) timeouts
    return _session

@lru_cache(maxsize=128)
def get_video_metadata(video_id: str) -> Dict:
    """
    Get video metadata with caching to reduce API calls.
    Optimized for time complexity O(1) with cache hits.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before fetching video metadata")
        cleanup_memory()
    
    url = f"https://api.vimeo.com/videos/{video_id}"
    try:
        session = get_session()
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        log_memory_usage(f"video metadata fetch for {video_id}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch video metadata for %s: %s", video_id, str(e))
        cleanup_memory()
        raise

@lru_cache(maxsize=64)
def list_captions(video_id: str) -> List[Dict]:
    """
    List captions with caching to reduce API calls.
    Optimized for time complexity O(1) with cache hits.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before listing captions")
        cleanup_memory()
    
    url = f"https://api.vimeo.com/videos/{video_id}/texttracks"
    try:
        session = get_session()
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        
        data = resp.json().get("data", [])
        log_memory_usage(f"captions list for {video_id}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to list captions for video %s: %s", video_id, str(e))
        cleanup_memory()
        return []

@lru_cache(maxsize=32)
def fetch_caption_text(caption_link: str) -> str:
    """
    Fetch caption text with caching to reduce API calls.
    Optimized for time complexity O(1) with cache hits.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before fetching caption text")
        cleanup_memory()
    
    try:
        session = get_session()
        resp = session.get(caption_link, timeout=30)
        resp.raise_for_status()
        
        # Return raw caption (SRT/VTT) text
        text = resp.text
        log_memory_usage(f"caption text fetch from {caption_link[:50]}...")
        return text
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch caption text from %s: %s", caption_link, str(e))
        cleanup_memory()
        raise

@lru_cache(maxsize=8)
def get_user_videos(limit: int = 3) -> List[Dict]:
    """
    Fetch videos from the authenticated user's account.
    Optimized with caching and connection pooling.
    
    Args:
        limit: Maximum number of videos to fetch
        
    Returns:
        List of video metadata dictionaries
        
    Raises:
        ValueError: If Vimeo access token is not configured
        requests.exceptions.RequestException: If API call fails
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before fetching user videos")
        cleanup_memory()
    
    # Early validation
    if not HEADERS or "Authorization" not in HEADERS:
        raise ValueError("Vimeo access token is not configured. Please set VIMEO_ACCESS_TOKEN in your .env file.")
    
    # Limit the number of videos to prevent memory issues
    max_limit = min(limit, 50)  # Cap at 50 videos
    
    url = "https://api.vimeo.com/me/videos"
    params = {
        "per_page": max_limit,
        "sort": "date",
        "direction": "desc"
    }
    
    try:
        session = get_session()
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        videos = data.get("data", [])
        
        # Clean up large response data
        del data
        gc.collect()
        
        logger.info("Fetched %d videos from Vimeo account", len(videos))
        log_memory_usage("user videos fetch")
        
        return videos
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Vimeo API authentication failed. Please check your VIMEO_ACCESS_TOKEN.")
            raise ValueError("Vimeo API authentication failed. Please check your VIMEO_ACCESS_TOKEN in .env file.")
        else:
            logger.error("Vimeo API HTTP error %d: %s", e.response.status_code, str(e))
            cleanup_memory()
            raise
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch user videos: %s", str(e))
        cleanup_memory()
        raise





