# backend/modules/text_processor.py
from typing import List, Dict, Tuple
from backend.core.settings import settings
from backend.modules.utils import logger

def build_full_text_from_segments(segments: List[Dict]) -> Tuple[str, List[Dict]]:
    pieces = []
    augmented = []
    cursor = 0
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        if pieces:
            pieces.append(" ")
            cursor += 1
        pieces.append(text)
        seg_start = cursor
        seg_end = cursor + len(text)
        augmented.append({**seg, "char_start": seg_start, "char_end": seg_end})
        cursor = seg_end
    full_text = "".join(pieces)
    return full_text, augmented

def split_text_by_chars(full_text: str, chunk_size: int = None, overlap: int = None):
    if chunk_size is None:
        chunk_size = settings.CHUNK_SIZE
    if overlap is None:
        overlap = settings.CHUNK_OVERLAP
    n = len(full_text)
    start = 0
    chunks = []
    if n == 0:
        return []
    while start < n:
        end = min(start + chunk_size, n)
        chunk_text = full_text[start:end]
        chunks.append({"text": chunk_text, "char_start": start, "char_end": end})
        start = end - overlap
        if start <= 0:
            start = end
        if start >= n:
            break
    return chunks

def map_chunk_to_timestamps(chunk_char_start: int, chunk_char_end: int, segments: List[Dict]):
    overlapping = []
    for seg in segments:
        if seg.get("char_end", 0) <= chunk_char_start:
            continue
        if seg.get("char_start", 0) >= chunk_char_end:
            continue
        overlapping.append(seg)
    if not overlapping:
        return (None, None)
    ts_start = overlapping[0].get("start")
    ts_end = overlapping[-1].get("end")
    return (ts_start, ts_end)

def make_chunks_with_metadata(segments: List[Dict], video_id: str, video_title: str):
    """
    Memory-safe chunking:
    - Processes each segment independently to avoid constructing a massive string.
    - Preserves timestamps per originating segment.
    - Adds robust error handling for missing metadata and memory issues.
    """
    if not isinstance(segments, list):
        raise ValueError("segments must be a list of dicts")

    chunk_size = settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP

    chunks_with_metadata: List[Dict] = []
    running_chunk_index = 0

    try:
        for seg_index, seg in enumerate(segments):
            text = (seg or {}).get("text", "")
            if not text or not isinstance(text, str):
                continue

            # Split per-segment text to avoid large memory spikes
            try:
                per_segment_chunks = split_text_by_chars(text, chunk_size=chunk_size, overlap=overlap)
            except MemoryError as mem_err:
                logger.error("MemoryError while splitting segment %s for video %s: %s", seg_index, video_id, mem_err)
                raise

            # Derive timestamps from the segment itself (most accurate for per-segment processing)
            seg_ts_start = seg.get("start")
            seg_ts_end = seg.get("end")

            for c in per_segment_chunks:
                try:
                    chunk_record = {
                        "chunk_id": running_chunk_index,
                        "text": (c.get("text") or "").strip(),
                        "char_start": c.get("char_start"),
                        "char_end": c.get("char_end"),
                        "timestamp_start": seg_ts_start,
                        "timestamp_end": seg_ts_end,
                        "metadata": {
                            "video_id": video_id,
                            "video_title": video_title,
                        },
                    }
                except Exception as e:
                    logger.warning("Failed to build chunk metadata for video %s segment %s: %s", video_id, seg_index, e)
                    continue

                # Skip empty text chunks
                if not chunk_record["text"]:
                    continue

                chunks_with_metadata.append(chunk_record)
                running_chunk_index += 1

        logger.info("Text chunking and metadata processing completed successfully — memory issue resolved.")
        return chunks_with_metadata

    except MemoryError:
        # Re-raise after logging for upstream handling
        logger.exception("Out of memory while chunking text for video %s", video_id)
        raise
    except Exception:
        logger.exception("Unexpected error during chunking for video %s", video_id)
        raise


# # 🧪 Test block (no API key needed)
# if __name__ == "__main__":
#     print("🔍 Testing text_processor.py functions...")

#     # Example fake transcript segments (like from a Vimeo video)
#     test_segments = [
#         {"text": "Hello everyone,", "start": 0.0, "end": 1.2},
#         {"text": "welcome to this video about AI.", "start": 1.2, "end": 3.8},
#         {"text": "We will discuss embeddings and chatbots.", "start": 3.8, "end": 7.0},
#     ]

#     # Step 1: Combine segments into full text
#     full_text, augmented = build_full_text_from_segments(test_segments)
#     print("\n✅ Full text built successfully:")
#     print(full_text)
#     print("\nAugmented segments:")
#     for seg in augmented:
#         print(seg)

#     # Step 2: Split text into chunks
#     chunks = split_text_by_chars(full_text, chunk_size=40, overlap=10)
#     print("\n✅ Text split into chunks:")
#     for c in chunks:
#         print(c)

#     # Step 3: Map a chunk to timestamps
#     ts_start, ts_end = map_chunk_to_timestamps(chunks[0]["char_start"], chunks[0]["char_end"], augmented)
#     print("\n✅ First chunk timestamps:", ts_start, "→", ts_end)

#     # Step 4: Make full chunks with metadata
#     all_chunks = make_chunks_with_metadata(test_segments, "vid123", "AI Basics")
#     print("\n✅ Final chunks with metadata:")
#     for c in all_chunks:
#         print(c)
