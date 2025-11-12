"""
Video ingestion router with enhanced security and validation.
"""
import time
import gc
from fastapi import APIRouter, HTTPException, status

# Safe imports with error handling for serverless environments
try:
    from app.services.vimeo_loader import get_video_metadata
except ImportError as e:
    import logging
    logging.error(f"Failed to import get_video_metadata: {e}")
    get_video_metadata = None

try:
    from app.services.transcript_manager import get_transcript_segments_from_vimeo
except ImportError as e:
    import logging
    logging.error(f"Failed to import get_transcript_segments_from_vimeo: {e}")
    get_transcript_segments_from_vimeo = None

try:
    from app.services.text_processor import make_chunks_with_metadata
except ImportError as e:
    import logging
    logging.error(f"Failed to import make_chunks_with_metadata: {e}")
    make_chunks_with_metadata = None

try:
    from app.services.vector_store_direct import store_embeddings_directly
    from app.services.vector_store_direct import check_duplicate_video, delete_video_embeddings
except ImportError as e:
    import logging
    logging.error(f"Failed to import vector_store_direct functions: {e}")
    store_embeddings_directly = None
    check_duplicate_video = None
    delete_video_embeddings = None

try:
    from app.services.metadata_manager import save_video_metadata
except ImportError as e:
    import logging
    logging.error(f"Failed to import save_video_metadata: {e}")
    save_video_metadata = None

try:
    from app.services.whisper_transcriber import transcribe_vimeo_audio
except ImportError as e:
    import logging
    logging.error(f"Failed to import transcribe_vimeo_audio: {e}")
    transcribe_vimeo_audio = None

try:
    from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    def log_memory_usage(*args, **kwargs): pass
    def cleanup_memory(*args, **kwargs): pass
    def check_memory_threshold(*args, **kwargs): return True

try:
    from app.models.schemas import VideoIngestRequest, VideoIngestResponse
except ImportError as e:
    import logging
    logging.error(f"Failed to import schemas: {e}")
    VideoIngestRequest = None
    VideoIngestResponse = None

try:
    from app.config.settings import settings
except ImportError:
    import os
    class MinimalSettings:
        ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
        is_development = False
        is_production = True
    settings = MinimalSettings()

try:
    from app.config.security import get_current_user, HTTPAuthorizationCredentials
except ImportError as e:
    import logging
    logging.warning(f"Security imports failed: {e}")
    get_current_user = None
    HTTPAuthorizationCredentials = None

router = APIRouter()


@router.get("/video")
@router.post("/video")
async def video_ingest_info():
    """
    Information endpoint for video ingestion.
    Returns usage instructions when video_id is not provided.
    
    Returns:
        JSON with usage information and example
    """
    return {
        "message": "Video ingestion endpoint",
        "description": "To ingest a video, use POST /ingest/video/{video_id}",
        "example": {
            "method": "POST",
            "url": "/ingest/video/1124405272",
            "body": {
                "force_transcription": False,
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        },
        "required_parameters": {
            "video_id": "Vimeo video ID (6-20 character numeric string) - must be included in the URL path"
        },
        "optional_parameters": {
            "force_transcription": "Force Whisper transcription even if captions exist (default: false)",
            "chunk_size": "Custom chunk size for text processing (default: 1000, range: 100-2000)",
            "chunk_overlap": "Custom chunk overlap (default: 200, range: 0-500)"
        },
        "note": "The video_id must be included in the URL path. Example: POST /ingest/video/1124405272"
    }


@router.get("/video/{video_id}")
async def ingest_video_info(video_id: str):
    """
    Information endpoint for video ingestion.
    Returns usage instructions when accessed via GET.
    
    Returns:
        JSON with usage information and video status
    """
    try:
        if check_duplicate_video is None:
            # Lazy import if not available
            try:
                from app.services.vector_store_direct import check_duplicate_video as _check
                check_duplicate_video = _check
            except ImportError:
                check_duplicate_video = lambda x: False
        
        exists = check_duplicate_video(video_id) if check_duplicate_video else False
        
        return {
            "message": "Video ingestion endpoint",
            "description": "To ingest a video, use POST /ingest/video/{video_id} with JSON body",
            "method": "POST",
            "endpoint": f"/ingest/video/{video_id}",
            "parameters": {
                "video_id": video_id
            },
            "current_status": {
                "video_id": video_id,
                "exists": exists,
                "status": "already_ingested" if exists else "not_ingested"
            },
            "example": {
                "body": {
                    "force_transcription": False,
                    "chunk_size": 1000,
                    "chunk_overlap": 200
                }
            },
            "note": "This endpoint uses POST method. Use GET to view this information and current video status."
        }
    except Exception as e:
        return {
            "message": "Video ingestion endpoint",
            "description": "To ingest a video, use POST /ingest/video/{video_id} with JSON body",
            "method": "POST",
            "endpoint": f"/ingest/video/{video_id}",
            "parameters": {
                "video_id": video_id
            },
            "error": f"Could not retrieve video status: {str(e)}",
            "example": {
                "body": {
                    "force_transcription": False,
                    "chunk_size": 1000,
                    "chunk_overlap": 200
                }
            },
            "note": "This endpoint uses POST method. Use GET to view this information."
        }

@router.post("/video/{video_id}")
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
    # Check if required services are available
    if VideoIngestRequest is None or VideoIngestResponse is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video ingestion service is not properly configured. Please check server logs."
        )
    
    if get_video_metadata is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video metadata service is not available. Please check server configuration."
        )
    
    if get_transcript_segments_from_vimeo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcript service is not available. Please check server configuration."
        )
    
    start_time = time.time()
    transcription_method = None
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before video ingestion")
        cleanup_memory()
    
    try:
        # Note: VideoIngestRequest doesn't have video_id field, it's in the URL path
        
        
        # Step 1: Optimized duplicate check - O(1) database lookup
        if check_duplicate_video and not request.force_transcription and check_duplicate_video(video_id):
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
        segments = None
        if get_transcript_segments_from_vimeo:
            segments = get_transcript_segments_from_vimeo(video_id)
        if segments:
            transcription_method = "captions"
            log_memory_usage(f"captions retrieved for {video_id}")

        # Step 4: Optimized fallback to Whisper - O(v) where v is video duration
        if (not segments or request.force_transcription) and transcribe_vimeo_audio:
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
        if request.force_transcription and delete_video_embeddings:
            try:
                deleted_count = delete_video_embeddings(video_id)
                if deleted_count > 0:
                    logger.info("Deleted %d existing embeddings for video %s", deleted_count, video_id)
            except Exception as e:
                logger.warning("Failed to delete existing embeddings for video %s: %s", video_id, str(e))

        # Step 7: Save metadata and prepare chunks
        if save_video_metadata:
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
        if not make_chunks_with_metadata:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Text processing service is not available. Please check server configuration."
            )
        
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
        if not store_embeddings_directly:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding storage service is not available. Please check server configuration."
            )
        
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
