# backend/modules/vector_store.py
import time
from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import SupabaseVectorStore
from backend.modules.embedding_manager import get_embeddings_instance
from backend.core.supabase_client import get_supabase
from backend.core.settings import settings
from backend.modules.utils import logger

def create_and_upload_to_supabase(chunks: list, table_name: str = None, max_retries: int = 3) -> SupabaseVectorStore:
    """
    Upload chunks to Supabase with retry logic and error handling.
    
    Args:
        chunks: list of dicts {text, metadata (video_id, video_title), chunk_id, timestamp_start, timestamp_end}
        table_name: Supabase table name (defaults to settings.SUPABASE_TABLE)
        max_retries: Maximum number of retry attempts
        
    Returns:
        SupabaseVectorStore instance
        
    Raises:
        Exception: If upload fails after all retries
    """
    if table_name is None:
        table_name = settings.SUPABASE_TABLE

    if not chunks:
        logger.warning("No chunks provided for upload")
        raise ValueError("No chunks provided for upload")

    texts = [c["text"] for c in chunks]
    metadatas = [
        {
            "video_id": c["metadata"]["video_id"],
            "video_title": c["metadata"]["video_title"],
            "chunk_id": c["chunk_id"],
            "timestamp_start": c["timestamp_start"],
            "timestamp_end": c["timestamp_end"]
        }
        for c in chunks
    ]
    
    logger.info("Preparing to upload %d chunks to Supabase table '%s'", len(texts), table_name)
    logger.info("Video IDs: %s", list(set(c["metadata"]["video_id"] for c in chunks)))
    
    # Retry logic for upload
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info("Upload attempt %d/%d", attempt + 1, max_retries)
            
            # Get embeddings instance
            embeddings = get_embeddings_instance()
            logger.info("Embeddings instance created successfully")
            
            # Get Supabase client
            supabase_client = get_supabase()
            logger.info("Supabase client created successfully")
            
            # Create and upload to Supabase
            vs = SupabaseVectorStore.from_texts(
                texts=texts,
                embedding=embeddings,
                metadatas=metadatas,
                client=supabase_client,
                table_name=table_name
            )
            
            logger.info("SUCCESS: Uploaded %d chunks to Supabase table '%s'", len(texts), table_name)
            return vs
            
        except Exception as e:
            last_exception = e
            logger.error("Upload attempt %d/%d failed: %s", attempt + 1, max_retries, str(e))
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info("Retrying in %d seconds...", wait_time)
                time.sleep(wait_time)
            else:
                logger.error("All upload attempts failed")
    
    # If we get here, all retries failed
    logger.error("Failed to upload chunks after %d attempts", max_retries)
    raise Exception(f"Failed to upload chunks to Supabase after {max_retries} attempts. Last error: {last_exception}")

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
        supabase_client = get_supabase()
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
        supabase_client = get_supabase()
        result = supabase_client.table(table_name).delete().eq("video_id", video_id).execute()
        deleted_count = len(result.data) if result.data else 0
        logger.info("Deleted %d embeddings for video %s", deleted_count, video_id)
        return deleted_count
    except Exception as e:
        logger.error("Failed to delete embeddings for video %s: %s", video_id, str(e))
        raise

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
        supabase_client = get_supabase()
        
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

def load_supabase_vectorstore(table_name: str = None):
    if table_name is None:
        table_name = settings.SUPABASE_TABLE
    embeddings = get_embeddings_instance()
    
    # Create a custom vector store that uses our match_video_embeddings function
    class CustomSupabaseVectorStore(SupabaseVectorStore):
        def similarity_search_by_vector_with_relevance_scores(
            self, 
            embedding: list, 
            k: int = 4, 
            filter: dict = None
        ):
            """Custom similarity search using our match_video_embeddings function."""
            try:
                # Use our custom function (the second function doesn't accept match_threshold)
                result = self._client.rpc(
                    'match_video_embeddings',
                    {
                        'query_embedding': embedding,
                        'match_count': k
                    }
                ).execute()
                
                if not result.data:
                    return []
                
                # Convert to LangChain document format
                from langchain.schema import Document
                import numpy as np
                docs = []
                for row in result.data:
                    metadata = {
                        'video_id': row.get('video_id'),
                        'video_title': row.get('video_title'),
                        'chunk_id': row.get('chunk_id'),
                        'timestamp_start': row.get('timestamp_start'),
                        'timestamp_end': row.get('timestamp_end')
                    }
                    doc = Document(
                        page_content=row.get('content', ''),
                        metadata=metadata
                    )
                    
                    # Calculate similarity score manually if not provided
                    similarity_score = row.get('similarity', None)
                    if similarity_score is None:
                        # Calculate cosine similarity manually
                        stored_embedding = row.get('embedding', [])
                        
                        # Handle string embeddings (they might be serialized)
                        if isinstance(stored_embedding, str):
                            try:
                                # Try to parse as JSON array
                                import json
                                stored_embedding = json.loads(stored_embedding)
                            except (json.JSONDecodeError, TypeError):
                                # If not JSON, try to parse as space-separated values
                                try:
                                    stored_embedding = [float(x) for x in stored_embedding.split()]
                                except (ValueError, AttributeError):
                                    stored_embedding = []
                        
                        if stored_embedding and len(stored_embedding) == len(embedding):
                            # Convert to numpy arrays for calculation
                            query_vec = np.array(embedding)
                            stored_vec = np.array(stored_embedding)
                            
                            # Normalize embeddings for better similarity calculation
                            query_norm = np.linalg.norm(query_vec)
                            stored_norm = np.linalg.norm(stored_vec)
                            
                            if query_norm > 0:
                                query_vec = query_vec / query_norm
                            if stored_norm > 0:
                                stored_vec = stored_vec / stored_norm
                            
                            # Calculate cosine similarity (dot product of normalized vectors)
                            similarity_score = np.dot(query_vec, stored_vec)
                            
                            # Ensure similarity is between 0 and 1
                            similarity_score = max(0.0, min(1.0, similarity_score))
                        else:
                            similarity_score = 0.0
                    
                    # Apply local threshold filtering (since Supabase function has high threshold)
                    if similarity_score >= 0.2:  # Local threshold filtering
                        docs.append((doc, similarity_score))
                
                return docs
                
            except Exception as e:
                logger.error(f"Custom similarity search failed: {e}")
                # Fallback to empty results
                return []
    
    vs = CustomSupabaseVectorStore(client=get_supabase(), embedding=embeddings, table_name=table_name)
    return vs







# if __name__ == "__main__":
#     print(" Testing vector_store.py ...")

#     # Fake chunks to simulate real data
#     sample_chunks = [
#         {
#             "text": "AI is transforming industries.",
#             "metadata": {"video_id": "v001", "video_title": "AI Overview"},
#             "chunk_id": 0,
#             "timestamp_start": "00:00:01",
#             "timestamp_end": "00:00:05"
#         },
#         {
#             "text": "Machine learning improves predictions.",
#             "metadata": {"video_id": "v001", "video_title": "AI Overview"},
#             "chunk_id": 1,
#             "timestamp_start": "00:00:05",
#             "timestamp_end": "00:00:10"
#         }
#     ]

#     # Just simulate upload without actually calling Supabase
#     try:
#         print(" Simulated upload process:")
#         for c in sample_chunks:
#             print(f"- {c['text']} ({c['metadata']['video_title']})")
#         print(" Supabase connection not attempted (offline mode).")
#     except Exception as e:
#         print(" Error:", e)
