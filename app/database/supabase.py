from typing import Optional, Any
from app.config.settings import settings
from app.services.vector_store_direct import get_supabase_direct

# Use the direct postgrest client as the main Supabase client
# This avoids the compatibility issues with the main Supabase library
_supabase_client: Optional[Any] = None

def get_supabase():
    """Get Supabase client singleton with validation."""
    global _supabase_client
    
    if _supabase_client is None:
        url_valid = settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("your_")
        key_valid = settings.SUPABASE_SERVICE_KEY and not settings.SUPABASE_SERVICE_KEY.startswith("your_")
        
        if not url_valid:
            raise ValueError("SUPABASE_URL is not properly configured. Please set a valid Supabase URL in your .env file.")
        
        if not key_valid:
            raise ValueError("SUPABASE_SERVICE_KEY is not properly configured. Please set a valid Supabase service key in your .env file.")
        
        try:
            _supabase_client = get_supabase_direct()
        except Exception as e:
            raise ValueError(f"Failed to create Supabase client: {e}. Please check your SUPABASE_URL and SUPABASE_SERVICE_KEY.")
    
    return _supabase_client


def test_connection():
    """Test if Supabase is reachable and table exists."""
    from app.utils.logger import logger
    try:
        resp = get_supabase().table("video_embeddings").select("*").limit(1).execute()
        logger.info(f"Supabase connection OK. Table returned {len(resp.data)} rows.")
        if resp.data:
            logger.debug(f"Sample data: {resp.data[0]}")
        else:
            logger.info("Table exists but no data yet.")
        return True
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        return False
