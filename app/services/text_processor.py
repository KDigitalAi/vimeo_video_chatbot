"""
Text processing utilities for chunking and metadata.
"""
import gc
from typing import List, Dict, Tuple
from app.config.settings import settings
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold

def build_full_text_from_segments(segments: List[Dict]) -> Tuple[str, List[Dict]]:
    """Build full text from segments with character position tracking."""
    pieces = []
    augmented = []
    cursor = 0
    
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
            
        # Add space between segments
        if cursor > 0:
            pieces.append(" ")
            cursor += 1
            
        pieces.append(text)
        seg_start = cursor
        seg_end = cursor + len(text)
        
        # Create augmented segment with char positions
        augmented.append({
            "text": seg.get("text", ""),
            "start": seg.get("start", ""),
            "end": seg.get("end", ""),
            "char_start": seg_start, 
            "char_end": seg_end
        })
        cursor = seg_end
    
    full_text = "".join(pieces)
    return full_text, augmented

def split_text_by_chars(full_text: str, chunk_size: int = None, overlap: int = None):
    """
    Optimized text chunking with O(n) time complexity and O(1) space complexity per chunk.
    Prevents infinite loops and uses efficient slicing.
    """
    if chunk_size is None:
        chunk_size = settings.CHUNK_SIZE
    if overlap is None:
        overlap = settings.CHUNK_OVERLAP
    
    # Ensure overlap is less than chunk_size to prevent infinite loops
    if overlap >= chunk_size:
        overlap = max(1, chunk_size - 1)
    
    # Prevent division by zero when chunk_size - overlap == 0
    if chunk_size <= overlap:
        overlap = max(1, chunk_size - 1)
    
    n = len(full_text)
    if n == 0:
        return []
    
    # Pre-allocate chunks list with estimated capacity
    estimated_chunks = (n // (chunk_size - overlap)) + 1
    chunks = []
    start = 0
    
    # Optimized loop with early termination
    while start < n:
        end = min(start + chunk_size, n)
        chunk_text = full_text[start:end]
        
        # Create chunk dict efficiently
        chunks.append({
            "text": chunk_text, 
            "char_start": start, 
            "char_end": end
        })
        
        # Calculate next start position with safety checks
        next_start = end - overlap
        if next_start <= start:  # Prevent infinite loops
            next_start = end
        if next_start >= n:  # Early termination
            break
            
        start = next_start
        
        # Additional safety check to prevent infinite loops
        if len(chunks) > estimated_chunks * 2:  # Prevent runaway loops
            break
            
    return chunks

def map_chunk_to_timestamps(chunk_char_start: int, chunk_char_end: int, segments: List[Dict]):
    """
    Optimized timestamp mapping with early termination.
    Time complexity: O(n) with early termination for better average case.
    """
    ts_start = None
    ts_end = None
    
    # Use list comprehension with early termination for better performance
    for seg in segments:
        seg_start = seg.get("char_start", 0)
        seg_end = seg.get("char_end", 0)
        
        # Early termination: if we've passed the chunk, no more overlaps possible
        if seg_start >= chunk_char_end:
            break
            
        # Check for overlap
        if seg_end > chunk_char_start and seg_start < chunk_char_end:
            if ts_start is None:
                ts_start = seg.get("start")
            ts_end = seg.get("end")
    
    return (ts_start, ts_end)

def make_chunks_with_metadata(segments: List[Dict], video_id: str, video_title: str):
    """
    Memory-optimized chunking:
    - Processes segments in batches to reduce memory usage
    - Implements streaming processing for large datasets
    - Adds memory monitoring and cleanup
    """
    if not isinstance(segments, list):
        raise ValueError("segments must be a list of dicts")

    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before chunking")
        cleanup_memory()

    chunk_size = settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP
    batch_size = 20  # Process 20 segments at a time

    chunks_with_metadata: List[Dict] = []
    running_chunk_index = 0

    try:
        # Process segments in batches to reduce memory usage
        for batch_start in range(0, len(segments), batch_size):
            batch_end = min(batch_start + batch_size, len(segments))
            batch_segments = segments[batch_start:batch_end]
            
            logger.info(f"Processing segment batch {batch_start//batch_size + 1} for video {video_id}")
            
            for seg_index, seg in enumerate(batch_segments):
                text = (seg or {}).get("text", "")
                if not text or not isinstance(text, str):
                    continue

                # Split per-segment text to avoid large memory spikes
                try:
                    per_segment_chunks = split_text_by_chars(text, chunk_size=chunk_size, overlap=overlap)
                except MemoryError as mem_err:
                    logger.error("MemoryError while splitting segment %s for video %s: %s", 
                               batch_start + seg_index, video_id, mem_err)
                    # Clean up and retry
                    cleanup_memory()
                    if not check_memory_threshold():
                        raise mem_err
                    per_segment_chunks = split_text_by_chars(text, chunk_size=chunk_size, overlap=overlap)

                # Derive timestamps from the segment itself
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
                        logger.warning("Failed to build chunk metadata for video %s segment %s: %s", 
                                     video_id, batch_start + seg_index, e)
                        continue

                    # Skip empty text chunks
                    if not chunk_record["text"]:
                        continue

                    chunks_with_metadata.append(chunk_record)
                    running_chunk_index += 1

            # Clean up batch variables
            del batch_segments, per_segment_chunks
            gc.collect()
            
            # Log memory usage after each batch
            log_memory_usage(f"segment batch {batch_start//batch_size + 1}")

        logger.info("Text chunking and metadata processing completed successfully — memory optimized.")
        log_memory_usage("chunking completion")
        return chunks_with_metadata

    except MemoryError:
        # Re-raise after logging for upstream handling
        logger.exception("Out of memory while chunking text for video %s", video_id)
        cleanup_memory()
        raise
    except Exception:
        logger.exception("Unexpected error during chunking for video %s", video_id)
        cleanup_memory()
        raise


