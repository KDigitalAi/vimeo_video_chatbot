# backend/modules/metadata_manager.py
import json
from pathlib import Path
from backend.modules.utils import logger

META_DIR = Path("backend/data/metadata")
META_DIR.mkdir(parents=True, exist_ok=True)

def save_video_metadata(video_id: str, metadata: dict):
    p = META_DIR / f"{video_id}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved metadata for video %s", video_id)
    return str(p)    

def load_video_metadata(video_id: str):
    p = META_DIR / f"{video_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))