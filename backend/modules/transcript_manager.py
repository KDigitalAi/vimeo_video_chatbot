# backend/modules/transcript_manager.py
from typing import List, Dict
from backend.modules.vimeo_loader import list_captions, fetch_caption_text
from backend.modules.utils import logger

def parse_srt_basic(srt_text: str) -> List[Dict]:
    """
    Minimal parser for SRT-like text. Produces segments with keys:
      {"text": str, "start": "HH:MM:SS", "end": "HH:MM:SS"}
    For production, replace with robust parser (pysrt/webvtt).
    """
    segments = []
    blocks = [b.strip() for b in srt_text.split("\n\n") if b.strip()]
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        # time line often second line (index may exist)
        time_line = None
        if "-->" in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        elif len(lines) > 1 and "-->" in lines[1]:
            time_line = lines[1]
            text_lines = lines[2:]
        else:
            # can't parse times robustly, skip
            continue
        start_raw, _, end_raw = time_line.partition("-->")
        start = start_raw.strip().split(",")[0].split(".")[0]
        end = end_raw.strip().split(",")[0].split(".")[0]
        text = " ".join(l.strip() for l in text_lines if l.strip())
        if text:  # Only add segments with text
            segments.append({"text": text, "start": start, "end": end})
    return segments

def get_transcript_segments_from_vimeo(video_id: str):
    captions = list_captions(video_id)
    if not captions:
        logger.info("No captions found for video %s", video_id)
        return []
    # pick first available caption track (could be language filtered)
    caption = captions[0]
    link = caption.get("link")
    if not link:
        logger.warning("Caption track has no link for video %s", video_id)
        return []
    raw = fetch_caption_text(link)
    segments = parse_srt_basic(raw)
    logger.info("Parsed %d caption segments for video %s", len(segments), video_id)
    return segments
    





# # 🧪 Local test block (safe to run without Vimeo API)
# if __name__ == "__main__":
#     print("🔍 Testing transcript_manager.py (local parsing only)...")

#     # Fake .srt-like caption text
#     sample_srt = """1
# 00:00:00,000 --> 00:00:02,000
# Hello everyone,

# 2
# 00:00:02,000 --> 00:00:04,000
# Welcome to this video on AI.

# 3
# 00:00:04,000 --> 00:00:06,000
# Today we discuss embeddings.
# """

#     segments = parse_srt_basic(sample_srt)
#     print("\n✅ Parsed segments:")
#     for s in segments:
#         print(s)
