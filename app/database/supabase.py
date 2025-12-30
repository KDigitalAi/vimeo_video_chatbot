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
    """Test if Supabase is reachable and all required tables exist."""
    from app.utils.logger import logger
    results = {
        "connected": False,
        "tables": {},
        "errors": []
    }
    
    try:
        client = get_supabase()
        if client is None:
            logger.error("Supabase client is None")
            results["errors"].append("Supabase client is None")
            return results
        
        # Test all required tables
        required_tables = [
            "pdf_embeddings",
            "chat_history", 
            "user_queries",
            "user_profile"
        ]
        
        all_tables_ok = True
        for table_name in required_tables:
            try:
                resp = client.table(table_name).select("*").limit(1).execute()
                results["tables"][table_name] = {
                    "exists": True,
                    "accessible": True,
                    "row_count": len(resp.data) if resp.data else 0
                }
                logger.info(f"[OK] Table '{table_name}' is accessible (rows: {len(resp.data) if resp.data else 0})")
            except Exception as e:
                error_msg = str(e)
                results["tables"][table_name] = {
                    "exists": False,
                    "accessible": False,
                    "error": error_msg
                }
                results["errors"].append(f"Table '{table_name}': {error_msg}")
                logger.error(f"[ERROR] Table '{table_name}' failed: {error_msg}")
                all_tables_ok = False
        
        results["connected"] = all_tables_ok
        if all_tables_ok:
            logger.info("[OK] Supabase connection OK. All required tables are accessible.")
        else:
            logger.warning("[WARNING] Supabase connection partial. Some tables are not accessible.")
        
        return results
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[ERROR] Supabase connection failed: {error_msg}")
        results["errors"].append(f"Connection error: {error_msg}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return results
