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
                    
                    # Create PDF embedding record (PDF-only mode)
                    metadata = chunk.get("metadata", {})
                    record = {
                        "content": chunk["text"],
                        "embedding": embedding_vector,
                        "pdf_id": metadata.get("pdf_id"),
                        "pdf_title": metadata.get("pdf_title"),
                        "chunk_id": chunk["chunk_id"],
                        "page_number": metadata.get("page_number")
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

# Video-specific functions removed - PDF-only mode
# verify_storage() function removed - unused
