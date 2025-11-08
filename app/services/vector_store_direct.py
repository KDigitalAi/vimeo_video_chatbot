"""
Direct vector store operations for Supabase.
"""
import gc
from typing import List, Dict, Any, Optional
from functools import lru_cache
from app.services.embedding_manager import get_embeddings_instance
from app.config.settings import settings
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold

# Lazy import to reduce memory footprint
def _get_sync_postgrest_client():
    try:
        from postgrest import SyncPostgrestClient
        return SyncPostgrestClient
    except ImportError as e:
        logger.error(f"Failed to import SyncPostgrestClient: {e}")
        raise

# Connection pooling for better performance
_supabase_client = None

@lru_cache(maxsize=1)
def get_supabase_direct():
    """
    Get Supabase client using direct postgrest method.
    Cached to reduce connection overhead.
    """
    global _supabase_client
    if _supabase_client is None:
        # Check memory before creating client
        if not check_memory_threshold():
            logger.warning("Memory usage high before creating Supabase client")
            cleanup_memory()
        
        url = f"{settings.SUPABASE_URL}/rest/v1"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }
        
        SyncPostgrestClient = _get_sync_postgrest_client()
        _supabase_client = SyncPostgrestClient(url, headers=headers)
        log_memory_usage("Supabase client creation")
    
    return _supabase_client

def store_embeddings_directly(chunks: list, table_name: str = None) -> int:
    """
    Store embeddings directly in Supabase with batch processing.
    Optimized for memory efficiency and reduced time complexity.
    
    Args:
        chunks: list of dicts with text, metadata, chunk_id, timestamp_start, timestamp_end
        table_name: Supabase table name
        
    Returns:
        Number of embeddings stored
    """
    if table_name is None:
        table_name = settings.SUPABASE_TABLE

    if not chunks:
        logger.warning("No chunks provided for storage")
        return 0

    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before storing embeddings")
        cleanup_memory()

    try:
        # Get embeddings instance (cached)
        embeddings = get_embeddings_instance()
        supabase_client = get_supabase_direct()
        
        logger.info("Storing %d chunks directly in Supabase table '%s'", len(chunks), table_name)
        
        # Process chunks in batches to reduce memory usage
        batch_size = 25  # Smaller batches for direct storage
        total_stored = 0
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            
            # Prepare data for batch insert
            records = []
            for chunk in batch_chunks:
                try:
                    # Generate embedding for the text
                    embedding_vector = embeddings.embed_query(chunk["text"])
                    
                    # Create record with dynamic schema based on source type
                    metadata = chunk.get("metadata", {})
                    source_type = metadata.get("source_type", "video")
                    
                    if source_type == "pdf":
                        # PDF embedding record (without source_type column)
                        record = {
                            "content": chunk["text"],
                            "embedding": embedding_vector,
                            "pdf_id": metadata.get("pdf_id"),
                            "pdf_title": metadata.get("pdf_title"),
                            "chunk_id": chunk["chunk_id"],
                            "page_number": metadata.get("page_number")
                        }
                    else:
                        # Video embedding record (default)
                        record = {
                            "content": chunk["text"],
                            "embedding": embedding_vector,
                            "video_id": metadata.get("video_id"),
                            "video_title": metadata.get("video_title"),
                            "chunk_id": chunk["chunk_id"],
                            "timestamp_start": chunk.get("timestamp_start"),
                            "timestamp_end": chunk.get("timestamp_end")
                        }
                    records.append(record)
                    
                except Exception as e:
                    logger.warning(f"Failed to process chunk {chunk.get('chunk_id', 'unknown')}: {e}")
                    continue
            
            if records:
                # Insert batch records
                result = supabase_client.table(table_name).insert(records).execute()
                batch_stored = len(result.data) if result.data else 0
                total_stored += batch_stored
                
                # Clean up batch variables
                del records, batch_chunks
                gc.collect()
                
                log_memory_usage(f"embedding batch {i//batch_size + 1}")
        
        logger.info("SUCCESS: Stored %d embeddings directly in Supabase", total_stored)
        log_memory_usage("embedding storage completion")
        
        return total_stored
        
    except Exception as e:
        logger.error("Failed to store embeddings directly: %s", str(e))
        cleanup_memory()
        raise

def check_duplicate_video(video_id: str, table_name: str = None) -> bool:
    """
    Check if a video has already been processed and stored.
    
    Args:
        video_id: Video ID to check
        table_name: Supabase table name
        
    Returns:
        True if video exists, False otherwise
    """
    if table_name is None:
        table_name = settings.SUPABASE_TABLE
    
    try:
        supabase_client = get_supabase_direct()
        result = supabase_client.table(table_name).select("id").eq("video_id", video_id).limit(1).execute()
        exists = len(result.data) > 0
        logger.info("Video %s %s in database", video_id, "exists" if exists else "does not exist")
        return exists
    except Exception as e:
        logger.warning("Could not check for duplicate video %s: %s", video_id, str(e))
        return False

def delete_video_embeddings(video_id: str, table_name: str = None) -> int:
    """
    Delete all embeddings for a specific video.
    
    Args:
        video_id: Video ID to delete
        table_name: Supabase table name
        
    Returns:
        Number of deleted rows
    """
    if table_name is None:
        table_name = settings.SUPABASE_TABLE
    
    try:
        supabase_client = get_supabase_direct()
        result = supabase_client.table(table_name).delete().eq("video_id", video_id).execute()
        deleted_count = len(result.data) if result.data else 0
        logger.info("Deleted %d embeddings for video %s", deleted_count, video_id)
        return deleted_count
    except Exception as e:
        logger.error("Failed to delete embeddings for video %s: %s", video_id, str(e))
        raise

def verify_storage():
    """Verify that embeddings are stored in Supabase."""
    try:
        supabase_client = get_supabase_direct()
        
        # Query all stored embeddings
        result = supabase_client.table(settings.SUPABASE_TABLE).select("*").order("id", desc=True).execute()
        
        if result.data:
            logger.info(f"Found {len(result.data)} embeddings in Supabase table: {settings.SUPABASE_TABLE}")
            
            videos = {}
            for row in result.data:
                video_id = row.get("video_id")
                if video_id not in videos:
                    videos[video_id] = {
                        "title": row.get("video_title"),
                        "chunks": 0
                    }
                videos[video_id]["chunks"] += 1
            
            if settings.is_development:
                for video_id, info in videos.items():
                    logger.debug(f"Video: {info['title']} (ID: {video_id}): {info['chunks']} chunks")
            
            return True
        else:
            logger.warning("No embeddings found in Supabase table")
            return False
            
    except Exception as e:
        logger.error(f"Failed to verify storage: {e}")
        return False
