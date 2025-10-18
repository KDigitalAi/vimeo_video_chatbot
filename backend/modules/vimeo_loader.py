# backend/modules/vimeo_loader.py
import requests
from backend.core.settings import settings
from backend.modules.utils import logger
from backend.modules.whisper_transcriber import transcribe_vimeo_audio


# Validate Vimeo access token early
if not settings.VIMEO_ACCESS_TOKEN or settings.VIMEO_ACCESS_TOKEN.startswith("your_"):
    logger.warning("VIMEO_ACCESS_TOKEN is not properly configured. Vimeo API calls will fail.")
    HEADERS = {}
else:
    HEADERS = {"Authorization": f"Bearer {settings.VIMEO_ACCESS_TOKEN}"}

def get_video_metadata(video_id: str):
    url = f"https://api.vimeo.com/videos/{video_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch video metadata for %s: %s", video_id, str(e))
        raise

def list_captions(video_id: str):
    url = f"https://api.vimeo.com/videos/{video_id}/texttracks"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.exceptions.RequestException as e:
        logger.error("Failed to list captions for video %s: %s", video_id, str(e))
        return []

def fetch_caption_text(caption_link: str) -> str:
    try:
        resp = requests.get(caption_link, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        # Return raw caption (SRT/VTT) text
        return resp.text
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch caption text from %s: %s", caption_link, str(e))
        raise

def get_user_videos(limit: int = 3):
    """
    Fetch videos from the authenticated user's account.
    
    Args:
        limit: Maximum number of videos to fetch
        
    Returns:
        List of video metadata dictionaries
        
    Raises:
        ValueError: If Vimeo access token is not configured
        requests.exceptions.RequestException: If API call fails
    """
    # Early validation
    if not HEADERS or "Authorization" not in HEADERS:
        raise ValueError("Vimeo access token is not configured. Please set VIMEO_ACCESS_TOKEN in your .env file.")
    
    url = "https://api.vimeo.com/me/videos"
    params = {
        "per_page": limit,
        "sort": "date",
        "direction": "desc"
    }
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        videos = data.get("data", [])
        logger.info("Fetched %d videos from Vimeo account", len(videos))
        
        return videos
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Vimeo API authentication failed. Please check your VIMEO_ACCESS_TOKEN.")
            raise ValueError("Vimeo API authentication failed. Please check your VIMEO_ACCESS_TOKEN in .env file.")
        else:
            logger.error("Vimeo API HTTP error %d: %s", e.response.status_code, str(e))
            raise
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch user videos: %s", str(e))
        raise









# if __name__ == "__main__":
#     test_video_id = "1124405272"  # replace with a real Vimeo video ID that has captions
#     try:
#         print("Fetching video metadata...")
#         meta = get_video_metadata(test_video_id)
#         print("Title:", meta.get("name"))
#         print("Duration:", meta.get("duration"), "seconds")

#         print("\nListing captions...")
#         captions = list_captions(test_video_id)
#         for cap in captions:
#             print("-", cap.get("language"), cap.get("link"))

#         if captions:
#             print("\nFetching first caption text...")
#             cap_link = captions[0]["link"]
#             raw_text = fetch_caption_text(cap_link)
#             print("Caption snippet:\n", raw_text[:500])  # preview first 500 chars
#         else:
#             print("⚠️ No captions found for this video.")
#     except Exception as e:
#         logger.exception("Error testing Vimeo loader: %s", e)
#         print("❌ Error:", e)
