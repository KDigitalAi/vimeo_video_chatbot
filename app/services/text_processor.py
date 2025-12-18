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

# Video-specific chunking function removed - PDF-only mode
# PDFs use their own chunking logic in pdf_processor.py


