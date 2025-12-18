from typing import Optional, Any

# Lazy import to prevent circular dependencies and import-time failures
def _get_settings():
    """Lazy import of settings to prevent circular dependencies."""
    from app.config.settings import settings
    return settings

def _get_supabase_direct():
    """Lazy import of get_supabase_direct to prevent circular dependencies."""
    from app.services.vector_store_direct import get_supabase_direct
    return get_supabase_direct

# Use the direct postgrest client as the main Supabase client
# This avoids the compatibility issues with the main Supabase library
_supabase_client: Optional[Any] = None

def get_supabase():
    """Get Supabase client singleton with validation - serverless-safe."""
    global _supabase_client
    
    if _supabase_client is None:
        try:
            # Use lazy imports to prevent circular dependencies
            settings = _get_settings()
            get_supabase_direct = _get_supabase_direct()
            
            url_valid = settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("your_")
            key_valid = settings.SUPABASE_SERVICE_KEY and not settings.SUPABASE_SERVICE_KEY.startswith("your_")
            
            if not url_valid:
                from app.utils.logger import logger
                logger.warning("SUPABASE_URL is not properly configured")
                raise ValueError("SUPABASE_URL is not properly configured")
            
            if not key_valid:
                from app.utils.logger import logger
                logger.warning("SUPABASE_SERVICE_KEY is not properly configured")
                raise ValueError("SUPABASE_SERVICE_KEY is not properly configured")
            
            _supabase_client = get_supabase_direct()
        except Exception as e:
            from app.utils.logger import logger
            logger.error(f"Failed to create Supabase client: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    return _supabase_client


def test_connection():
    """Test if Supabase is reachable and pdf_embeddings table exists."""
    from app.utils.logger import logger
    try:
        resp = get_supabase().table("pdf_embeddings").select("*").limit(1).execute()
        logger.info(f"Supabase connection OK. PDF embeddings table returned {len(resp.data)} rows.")
        if resp.data:
            logger.debug(f"Sample data: {resp.data[0]}")
        else:
            logger.info("PDF embeddings table exists but no data yet.")
        return True
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        return False
