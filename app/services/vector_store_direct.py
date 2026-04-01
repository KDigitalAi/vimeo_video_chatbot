"""
Direct vector store operations for Supabase.
Embeddings are created only by the Assessment pipeline; this module does not insert into pdf_embeddings.
"""
from functools import lru_cache
from app.utils.logger import log_memory_usage
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe, memory_guard

settings = get_settings_safe()
logger = get_logger_safe(__name__)

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
        memory_guard(logger, "creating Supabase client")
        
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
    No-op: Embeddings are created only by the Assessment pipeline.
    Chatbot does not write to pdf_embeddings; duplicate embeddings are avoided.
    """
    if table_name is None:
        table_name = getattr(settings, "SUPABASE_TABLE", "pdf_embeddings")
    if chunks:
        logger.info(
            "Embeddings are managed by the Assessment system; skipping direct store (%d chunks, table=%s)",
            len(chunks), table_name
        )
    return 0

# Video-specific functions removed - PDF-only mode
# verify_storage() function removed - unused
