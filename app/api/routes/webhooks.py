from typing import Any, Dict, Optional
import os
import asyncio
import gc
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status, Request
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold
from app.services.vimeo_loader import get_video_metadata
from app.services.transcript_manager import get_transcript_segments_from_vimeo
from app.services.whisper_transcriber import transcribe_vimeo_audio
from app.services.text_processor import make_chunks_with_metadata
from app.services.vector_store_direct import (
    check_duplicate_video,
    store_embeddings_directly,
)


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _extract_video_id_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """
    Optimized video ID extraction with O(1) average case complexity.
    Handles various Vimeo webhook payload formats with early termination.
    """
    logger.info("Extracting video ID from payload")
    
    # Optimized candidate order based on frequency
    candidates = [
        payload.get("clip"),
        payload.get("video"), 
        payload.get("resource"),
        payload.get("data"),
        payload,  # Check the root payload as well
    ]
    
    # Optimized URI fields order
    uri_fields = ["uri", "resource_uri", "link", "url"]
    id_fields = ["video_id", "id", "clip_id", "videoId"]
    
    for node in candidates:
        if not isinstance(node, dict):
            continue
            
        # Try URI fields first (most common case)
        for uri_field in uri_fields:
            uri = node.get(uri_field)
            if isinstance(uri, str) and "/videos/" in uri:
                try:
                    video_id = uri.rstrip("/").split("/")[-1]
                    logger.info("Extracted video ID from %s: %s", uri_field, video_id)
                    return video_id
                except Exception:
                    continue
        
        # Try direct ID fields
        for id_field in id_fields:
            vid = node.get(id_field)
            if isinstance(vid, (str, int)) and str(vid).strip():
                video_id = str(vid).strip()
                logger.info("Extracted video ID from %s: %s", id_field, video_id)
                return video_id
    
    logger.warning("Could not extract video ID from any candidate in payload")
    return None


async def _process_video_async(video_id: str) -> None:
    """
    Asynchronously process a new Vimeo video upload.
    Optimized for memory efficiency and performance.
    
    This function handles the complete pipeline:
    1. Check for duplicates
    2. Fetch video metadata
    3. Extract audio and transcribe
    4. Generate embeddings
    5. Store in Supabase
    
    Args:
        video_id: The Vimeo video ID to process
    """
    logger.info("New video detected - Starting automatic processing pipeline for video_id: %s", video_id)
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before video processing")
        cleanup_memory()
    
    try:
        # Step 1: Check for duplicates
        logger.info("Checking for duplicate video_id: %s", video_id)
        if check_duplicate_video(video_id):
            logger.info("Video %s already processed - skipping to avoid duplicates", video_id)
            return
        
        # Step 2: Optimized metadata fetching - O(1) API call
        logger.info("Fetching video metadata for video_id: %s", video_id)
        try:
            meta = await asyncio.get_event_loop().run_in_executor(None, get_video_metadata, video_id)
            # Optimized metadata extraction with fallback chain
            video_title = meta.get("name", f"Video {video_id}")
            video_duration = meta.get("duration", 0)
            video_url = meta.get("link", f"https://vimeo.com/{video_id}")
            
            logger.info("Video metadata retrieved - Title: '%s', Duration: %ds, URL: %s", 
                       video_title, video_duration, video_url)
            log_memory_usage(f"metadata fetched for {video_id}")
        except Exception as e:
            logger.error("Failed to fetch video metadata for %s: %s", video_id, str(e))
            cleanup_memory()
            raise

        # Step 3: Optimized transcript retrieval with fallback - O(1) API call + O(v) transcription
        logger.info("Attempting to retrieve existing captions for video_id: %s", video_id)
        try:
            segments = await asyncio.get_event_loop().run_in_executor(
                None, get_transcript_segments_from_vimeo, video_id
            )
            if segments:
                logger.info("Found existing captions for video_id: %s (%d segments)", video_id, len(segments))
            else:
                logger.info("No existing captions found for %s, proceeding with audio transcription", video_id)
        except Exception as e:
            logger.warning("Failed to retrieve existing captions for %s: %s", video_id, str(e))
            segments = None

        # Step 4: Optimized Whisper fallback - O(v) where v is video duration
        if not segments:
            logger.info("Starting audio extraction and transcription for video_id: %s", video_id)
            try:
                segments = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_vimeo_audio, video_id
                )
                if segments:
                    logger.info("Audio transcription completed for video_id: %s (%d segments)", video_id, len(segments))
                else:
                    logger.warning("No transcript segments generated for video_id: %s", video_id)
            except Exception as e:
                logger.error("Audio transcription failed for video_id: %s: %s", video_id, str(e))
                raise

        if not segments:
            logger.warning("No transcript available for video %s - skipping processing", video_id)
            return

        # Step 5: Chunk the transcript text
        logger.info("Chunking transcript text for video_id: %s", video_id)
        try:
            chunks = await asyncio.get_event_loop().run_in_executor(
                None, make_chunks_with_metadata, segments, video_id, video_title
            )
            if chunks:
                logger.info("Text chunking completed for video_id: %s (%d chunks)", video_id, len(chunks))
                log_memory_usage(f"chunks created for {video_id}")
            else:
                logger.warning("No chunks produced for video_id: %s", video_id)
        except Exception as e:
            logger.error("Text chunking failed for video_id: %s: %s", video_id, str(e))
            cleanup_memory()
            raise

        if not chunks:
            logger.warning("No chunks produced for video %s - skipping embedding generation", video_id)
            return

        # Clean up segments to free memory
        del segments
        gc.collect()

        # Step 6: Generate embeddings and store in Supabase
        logger.info("Generating embeddings and storing in Supabase for video_id: %s", video_id)
        try:
            stored_count = await asyncio.get_event_loop().run_in_executor(
                None, store_embeddings_directly, chunks
            )
            if stored_count > 0:
                logger.info("SUCCESS: Automatic embedding storage completed for video_id: %s (%d embeddings stored)", 
                           video_id, stored_count)
                log_memory_usage(f"embeddings stored for {video_id}")
            else:
                logger.warning("Embedding storage returned 0 rows for video_id: %s", video_id)
        except Exception as e:
            logger.error("Embedding storage failed for video_id: %s: %s", video_id, str(e))
            cleanup_memory()
            raise
        
        # Clean up chunks to free memory
        del chunks
        gc.collect()

        logger.info("Video processing pipeline completed successfully for video_id: %s", video_id)
        
    except Exception as e:
        logger.error("Video processing pipeline failed for video_id: %s: %s", video_id, str(e))
        # Don't re-raise to prevent webhook from failing - log and continue
        logger.info("Continuing to process other videos despite error for video_id: %s", video_id)


@router.post("/vimeo")
async def vimeo_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_vimeo_signature: Optional[str] = Header(default=None),
):
    """
    Receive Vimeo webhooks (e.g., video.ready, video.transcoded) and trigger automatic processing.
    Optimized for memory efficiency and performance.
    
    This endpoint handles new video uploads and automatically:
    1. Fetches video metadata
    2. Extracts audio and transcribes with Whisper
    3. Generates embeddings using the configured model
    4. Stores embeddings in Supabase
    
    Security: If VIMEO_WEBHOOK_SECRET is set, require its match in a custom header
    (e.g., X-Webhook-Secret). This is a simple shared-secret approach.
    """
    if settings.is_development:
        logger.info("Vimeo webhook received")
        logger.debug("Request headers: %s", dict(request.headers))
        logger.debug("Request method: %s", request.method)
        logger.debug("Request URL: %s", str(request.url))
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before webhook processing")
        cleanup_memory()
    
    try:
        payload = await request.json()
        logger.info("Webhook payload received")
        logger.info("Webhook event type: %s", payload.get("type", "unknown"))
    except Exception as e:
        logger.error("Failed to parse webhook JSON: %s", str(e))
        cleanup_memory()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # Optional shared-secret check
    shared_secret = os.environ.get("VIMEO_WEBHOOK_SECRET")
    if shared_secret:
        provided = request.headers.get("X-Webhook-Secret")
        if not provided or provided != shared_secret:
            logger.warning("Webhook authentication failed - invalid secret")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    # Optimized video ID extraction - O(1) average case
    video_id = _extract_video_id_from_payload(payload)
    if not video_id:
        logger.warning("Vimeo webhook received but no video_id could be extracted from payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="video_id not found in payload")

    logger.info("Webhook processing initiated for video_id: %s", video_id)
    logger.info("Event type: %s", payload.get("type", "unknown"))

    # Trigger asynchronous background processing - O(1) task queuing
    background_tasks.add_task(_process_video_async, video_id)

    logger.info("Background task queued for video_id: %s", video_id)
    logger.info("=== WEBHOOK RESPONSE SENT ===")

    # Optimized response creation with minimal object creation
    return {
        "status": "accepted", 
        "video_id": video_id,
        "message": "Video processing pipeline started automatically",
        "webhook_type": payload.get("type", "unknown"),
        "timestamp": str(asyncio.get_event_loop().time())
    }


@router.get("/health")
async def webhook_health_check():
    """Health check endpoint for webhook system. Optimized for memory efficiency."""
    # Check memory status
    memory_ok = check_memory_threshold()
    
    return {
        "status": "ok" if memory_ok else "degraded",
        "webhook_system": "operational",
        "automatic_processing": "enabled",
        "memory_status": "ok" if memory_ok else "high_usage",
        "supported_events": ["video.ready", "video.transcoded", "video.uploaded"],
        "endpoints": {
            "webhook": "/webhooks/vimeo",
            "health": "/webhooks/health",
            "test": "/webhooks/test/{video_id}"
        }
    }


@router.post("/test/{video_id}")
async def manual_test_processing(
    video_id: str,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger video processing for testing purposes.
    Optimized for memory efficiency.
    
    This endpoint allows manual testing of the video processing pipeline
    without waiting for a webhook from Vimeo.
    
    Use this to test the complete pipeline with an existing Vimeo video ID.
    """
    logger.info("=== MANUAL TEST TRIGGER ===")
    logger.info("Manual processing trigger received for video_id: %s", video_id)
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before manual test processing")
        cleanup_memory()
    
    # Trigger the same async processing pipeline
    background_tasks.add_task(_process_video_async, video_id)
    
    logger.info("Background task queued for manual test video_id: %s", video_id)
    logger.info("=== MANUAL TEST RESPONSE SENT ===")
    
    return {
        "status": "triggered",
        "video_id": video_id,
        "message": "Manual processing pipeline started",
        "note": "This is for testing purposes - use Vimeo webhooks in production",
        "timestamp": str(asyncio.get_event_loop().time())
    }


