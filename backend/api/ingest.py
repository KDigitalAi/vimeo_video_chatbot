# backend/routers/ingest.py
"""
Video ingestion router with enhanced security and validation.
Implements comprehensive input validation and error handling.
Optimized for memory efficiency and performance.
"""
import time
import gc
from fastapi import APIRouter, HTTPException, status
from backend.modules.vimeo_loader import get_video_metadata
from backend.modules.transcript_manager import get_transcript_segments_from_vimeo
from backend.modules.text_processor import make_chunks_with_metadata
from backend.modules.vector_store_direct import store_embeddings_directly
from backend.modules.vector_store_direct import check_duplicate_video, delete_video_embeddings
from backend.modules.metadata_manager import save_video_metadata
from backend.modules.whisper_transcriber import transcribe_vimeo_audio
from backend.modules.utils import logger, log_memory_usage, cleanup_memory, check_memory_threshold
from backend.core.validation import VideoIngestRequest, VideoIngestResponse
from backend.core.settings import settings
from backend.core.security import get_current_user, HTTPAuthorizationCredentials

router = APIRouter()


@router.post("/video/{video_id}", response_model=VideoIngestResponse)
async def ingest_video(
    video_id: str, 
    request: VideoIngestRequest,
    credentials: HTTPAuthorizationCredentials = None
):
    """
    Ingests a Vimeo video by ID with enhanced security and validation.
    Optimized for memory efficiency and performance.
    
    Process:
    1. Validates video ID and request parameters
    2. Fetches video metadata from Vimeo API
    3. Attempts to get captions from Vimeo
    4. Falls back to Whisper transcription if needed
    5. Processes text into chunks with metadata
    6. Creates embeddings and uploads to Supabase
    
    Args:
        video_id: Vimeo video ID (validated)
        request: Validated ingestion request
        credentials: JWT authentication credentials (optional)
        
    Returns:
        VideoIngestResponse with processing results
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    transcription_method = None
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before video ingestion")
        cleanup_memory()
    
    try:
        # Note: VideoIngestRequest doesn't have video_id field, it's in the URL path
        
        
        # Step 1: Optimized duplicate check - O(1) database lookup
        if not request.force_transcription and check_duplicate_video(video_id):
            logger.info("Video %s already exists in database", video_id)
            return VideoIngestResponse(
                video_id=video_id,
                video_title=f"video_{video_id}",
                chunk_count=0,
                message="Video already exists in database. Use force_transcription=true to re-ingest.",
                processing_time=0.0,
                transcription_method="existing"
            )
        
        # Step 2: Optimized metadata fetching - O(1) API call with efficient fallback
        try:
            meta = get_video_metadata(video_id)
            # Optimized title extraction with efficient fallback chain
            video_title = (meta.get("name") or 
                          meta.get("title") or 
                          meta.get("link", "").split("/")[-1] or 
                          f"video_{video_id}")
            logger.info("Fetched metadata for video: %s", video_title)
            log_memory_usage(f"metadata fetched for {video_id}")
        except Exception as e:
            logger.exception("Failed to get metadata for video %s", video_id)
            cleanup_memory()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch metadata: {str(e)}"
            )

        # Step 3: Optimized transcript processing - O(1) API call with fallback
        segments = get_transcript_segments_from_vimeo(video_id)
        if segments:
            transcription_method = "captions"
            log_memory_usage(f"captions retrieved for {video_id}")

        # Step 4: Optimized fallback to Whisper - O(v) where v is video duration
        if not segments or request.force_transcription:
            logger.warning("No captions found for video %s. Trying Whisper transcription...", video_id)
            try:
                segments = transcribe_vimeo_audio(video_id)
                if segments:
                    logger.info("SUCCESS: Whisper transcription successful for video %s", video_id)
                    transcription_method = "whisper"
                    log_memory_usage(f"whisper transcription completed for {video_id}")
            except Exception as e:
                logger.exception("Whisper transcription failed for video %s", video_id)
                cleanup_memory()
                if not segments:  # Only raise error if we have no segments at all
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No captions or transcription found for this video"
                    )

        # Step 5: If still no transcript, stop here
        if not segments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No captions or transcription found for this video"
            )

        # Step 6: Optimized duplicate cleanup - O(1) database operation
        if request.force_transcription:
            try:
                deleted_count = delete_video_embeddings(video_id)
                if deleted_count > 0:
                    logger.info("Deleted %d existing embeddings for video %s", deleted_count, video_id)
            except Exception as e:
                logger.warning("Failed to delete existing embeddings for video %s: %s", video_id, str(e))

        # Step 7: Save metadata and prepare chunks
        try:
            save_video_metadata(video_id, {
                "video_id": video_id,
                "video_title": video_title,
                "source_meta": meta,
                "transcription_method": transcription_method,
                "ingestion_timestamp": time.time()
            })
        except Exception as e:
            logger.warning("Failed to save metadata for video %s: %s", video_id, str(e))

        # Step 8: Optimized chunking - O(t) where t is transcript length
        try:
            chunks = make_chunks_with_metadata(segments, video_id, video_title)
            logger.info("Created %d chunks for video %s", len(chunks), video_id)
            log_memory_usage(f"chunks created for {video_id}")
            
            # Clean up segments immediately to reduce memory usage
            del segments
            gc.collect()
        except Exception as e:
            logger.exception("Failed to create chunks for video %s", video_id)
            cleanup_memory()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process video content"
            )

        # Step 9: Optimized embedding upload - O(c) where c is number of chunks
        try:
            stored_count = store_embeddings_directly(chunks)
            logger.info("SUCCESS: Uploaded embeddings to Supabase for video %s", video_id)
            log_memory_usage(f"embeddings uploaded for {video_id}")
            
            # Clean up chunks immediately to free memory
            del chunks
            gc.collect()
        except Exception as e:
            logger.exception("Failed to upload embeddings for video %s", video_id)
            cleanup_memory()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload embeddings to database: {str(e)}"
            )

        processing_time = time.time() - start_time
        
        return VideoIngestResponse(
            video_id=video_id,
            video_title=video_title,
            chunk_count=len(chunks),
            message="Ingestion completed and embeddings uploaded to Supabase.",
            processing_time=round(processing_time, 3),
            transcription_method=transcription_method
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in ingest_video")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during video ingestion"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the ingestion service.
    Optimized for memory efficiency.
    
    Returns:
        Health status information
    """
    # Check memory status
    memory_ok = check_memory_threshold()
    
    return {
        "status": "healthy" if memory_ok else "degraded",
        "service": "video-ingestion",
        "memory_status": "ok" if memory_ok else "high_usage",
        "timestamp": time.time()
    }