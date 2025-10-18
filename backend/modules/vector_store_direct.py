# backend/modules/vector_store_direct.py
import time
from typing import List, Dict, Any, Optional
from postgrest import SyncPostgrestClient
from backend.modules.embedding_manager import get_embeddings_instance
from backend.core.settings import settings
from backend.modules.utils import logger

def get_supabase_direct():
    """Get Supabase client using direct postgrest method."""
    url = f"{settings.SUPABASE_URL}/rest/v1"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    return SyncPostgrestClient(url, headers=headers)

def store_embeddings_directly(chunks: list, table_name: str = None) -> int:
    """
    Store embeddings directly in Supabase with the specific schema:
    id, content, embedding, video_id, video_title, chunk_id, timestamp_start, timestamp_end
    
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

    try:
        # Get embeddings instance
        embeddings = get_embeddings_instance()
        supabase_client = get_supabase_direct()
        
        logger.info("Storing %d chunks directly in Supabase table '%s'", len(chunks), table_name)
        
        # Prepare data for batch insert
        records = []
        for chunk in chunks:
            # Generate embedding for the text
            embedding_vector = embeddings.embed_query(chunk["text"])
            
            # Create record with the specific schema
            record = {
                "content": chunk["text"],
                "embedding": embedding_vector,
                "video_id": chunk["metadata"]["video_id"],
                "video_title": chunk["metadata"]["video_title"],
                "chunk_id": chunk["chunk_id"],
                "timestamp_start": chunk.get("timestamp_start"),
                "timestamp_end": chunk.get("timestamp_end")
            }
            records.append(record)
        
        # Insert all records at once
        result = supabase_client.table(table_name).insert(records).execute()
        
        stored_count = len(result.data) if result.data else 0
        logger.info("SUCCESS: Stored %d embeddings directly in Supabase", stored_count)
        
        return stored_count
        
    except Exception as e:
        logger.error("Failed to store embeddings directly: %s", str(e))
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
            print(f"SUCCESS: Found {len(result.data)} embeddings in Supabase table")
            print(f"Table: {settings.SUPABASE_TABLE}")
            
            # Group by video
            videos = {}
            for row in result.data:
                video_id = row.get("video_id")
                if video_id not in videos:
                    videos[video_id] = {
                        "title": row.get("video_title"),
                        "chunks": 0
                    }
                videos[video_id]["chunks"] += 1
            
            print(f"\nVideos in database:")
            for video_id, info in videos.items():
                print(f"- {info['title']} (ID: {video_id}): {info['chunks']} chunks")
            
            return True
        else:
            print("WARNING: No embeddings found in Supabase table")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to verify storage: {e}")
        return False
