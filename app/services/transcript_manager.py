"""
Transcript management for Vimeo captions and transcripts.
"""
import re
from typing import List, Dict
from functools import lru_cache
from app.services.vimeo_loader import list_captions, fetch_caption_text
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold

def parse_srt_basic(srt_text: str) -> List[Dict]:
    """
    Optimized SRT parser with improved time complexity.
    Uses regex for better performance and memory efficiency.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before parsing SRT")
        cleanup_memory()
    
    segments = []
    
    try:
        # Use regex for more efficient parsing
        # Pattern to match SRT blocks: number, timestamp, text
        srt_pattern = re.compile(
            r'(\d+)\s*\n'  # Block number
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'  # Timestamps
            r'((?:.*\n?)*?)(?=\n\d+\s*\n|\Z)',  # Text content
            re.MULTILINE | re.DOTALL
        )
        
        matches = srt_pattern.findall(srt_text)
        
        for match in matches:
            try:
                block_num, start_time, end_time, text = match
                
                # Clean up text
                text = text.strip().replace('\n', ' ')
                
                # Convert timestamps to simpler format
                start = start_time.split(',')[0]  # Remove milliseconds
                end = end_time.split(',')[0]     # Remove milliseconds
                
                if text:  # Only add segments with text
                    segments.append({
                        "text": text,
                        "start": start,
                        "end": end
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to parse SRT block: {e}")
                continue
        
        # Fallback to original method if regex fails
        if not segments:
            logger.info("Regex parsing failed, using fallback method")
            segments = _parse_srt_fallback(srt_text)
        
        log_memory_usage(f"SRT parsing completed with {len(segments)} segments")
        return segments
        
    except Exception as e:
        logger.error(f"SRT parsing failed: {e}")
        cleanup_memory()
        return []

def _parse_srt_fallback(srt_text: str) -> List[Dict]:
    """Optimized fallback SRT parsing method for compatibility."""
    # Pre-filter empty blocks for better performance
    blocks = [b.strip() for b in srt_text.split("\n\n") if b.strip()]
    segments = []
    
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            continue
            
        # Find time line more efficiently
        time_line = None
        text_lines = []
        
        for i, line in enumerate(lines):
            if "-->" in line:
                time_line = line
                text_lines = lines[i+1:]
                break
        
        if not time_line:
            continue
            
        # Parse timestamps more efficiently
        start_raw, _, end_raw = time_line.partition("-->")
        start = start_raw.strip().split(",")[0].split(".")[0]
        end = end_raw.strip().split(",")[0].split(".")[0]
        
        # Join text lines more efficiently
        text = " ".join(line.strip() for line in text_lines if line.strip())
        
        if text:
            segments.append({"text": text, "start": start, "end": end})
    
    return segments

@lru_cache(maxsize=32)
def get_transcript_segments_from_vimeo(video_id: str) -> List[Dict]:
    """
    Get transcript segments from Vimeo with caching and optimization.
    Optimized for time complexity O(1) with cache hits.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before fetching transcript")
        cleanup_memory()
    
    try:
        captions = list_captions(video_id)
        if not captions:
            logger.info("No captions found for video %s", video_id)
            return []
        
        # Pick first available caption track (could be language filtered)
        caption = captions[0]
        link = caption.get("link")
        if not link:
            logger.warning("Caption track has no link for video %s", video_id)
            return []
        
        # Fetch caption text (cached)
        raw = fetch_caption_text(link)
        
        # Parse SRT with optimized algorithm
        segments = parse_srt_basic(raw)
        
        # Clean up large text data
        del raw
        gc.collect()
        
        logger.info("Parsed %d caption segments for video %s", len(segments), video_id)
        log_memory_usage(f"transcript parsing for {video_id}")
        
        return segments
        
    except Exception as e:
        logger.error(f"Failed to get transcript segments for video {video_id}: {e}")
        cleanup_memory()
        return []


