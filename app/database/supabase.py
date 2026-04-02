import time
from typing import Optional, Any
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe

logger = get_logger_safe(__name__)

# Lazy import to prevent circular dependencies and import-time failures
def _get_settings():
    """Lazy import of settings to prevent circular dependencies."""
    return get_settings_safe()

def _get_supabase_direct():
    """Lazy import of get_supabase_direct to prevent circular dependencies."""
    from app.services.adapters.vector_store_direct import get_supabase_direct
    return get_supabase_direct

# Use the direct postgrest client as the main Supabase client
# This avoids the compatibility issues with the main Supabase library
_supabase_client: Optional[Any] = None

def get_supabase():
    """Get Supabase client singleton with validation - serverless-safe."""
    global _supabase_client
    
    if _supabase_client is None:
        logger.info("Creating Supabase client", component="supabase")
        try:
            # Use lazy imports to prevent circular dependencies
            settings = _get_settings()
            get_supabase_direct = _get_supabase_direct()
            
            url_valid = settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("your_")
            key_valid = settings.SUPABASE_SERVICE_KEY and not settings.SUPABASE_SERVICE_KEY.startswith("your_")
            
            if not url_valid:
                logger.warning("SUPABASE_URL is not properly configured", component="supabase")
                raise ValueError("SUPABASE_URL is not properly configured")
            
            if not key_valid:
                logger.warning("SUPABASE_SERVICE_KEY is not properly configured", component="supabase")
                raise ValueError("SUPABASE_SERVICE_KEY is not properly configured")
            
            _supabase_client = get_supabase_direct()
            logger.info("Supabase client created", component="supabase")
        except Exception as e:
            logger.exception("Failed to create Supabase client", component="supabase")
            raise
    
    return _supabase_client


def test_connection():
    """Test if Supabase is reachable and all required tables exist."""
    results = {
        "connected": False,
        "tables": {},
        "errors": []
    }
    
    start_time = time.perf_counter()
    try:
        client = get_supabase()
        if client is None:
            logger.error("Supabase client is None", component="supabase")
            results["errors"].append("Supabase client is None")
            return results
        
        # Test all required tables
        required_tables = [
            "pdf_embeddings",
            "chatbot_chat_history",
            "chatbot_user_queries",
            "chatbot_user_profile",
        ]
        
        all_tables_ok = True
        for table_name in required_tables:
            table_start = time.perf_counter()
            try:
                logger.info(
                    f"Using table: {table_name}",
                    component="supabase",
                    operation="test_connection",
                    table_name=table_name,
                )
                resp = client.table(table_name).select("*").limit(1).execute()
                results["tables"][table_name] = {
                    "exists": True,
                    "accessible": True,
                    "row_count": len(resp.data) if resp.data else 0
                }
                logger.info(
                    "Supabase table accessible",
                    component="supabase",
                    table_name=table_name,
                    row_count=len(resp.data) if resp.data else 0,
                    query_duration_ms=round((time.perf_counter() - table_start) * 1000, 2),
                )
            except Exception as e:
                error_msg = str(e)
                results["tables"][table_name] = {
                    "exists": False,
                    "accessible": False,
                    "error": error_msg
                }
                results["errors"].append(f"Table '{table_name}': {error_msg}")
                logger.exception(
                    "Supabase table check failed",
                    component="supabase",
                    table_name=table_name,
                    query_duration_ms=round((time.perf_counter() - table_start) * 1000, 2),
                )
                all_tables_ok = False
        
        results["connected"] = all_tables_ok
        if all_tables_ok:
            logger.info(
                "Supabase connection healthy",
                component="supabase",
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
        else:
            logger.warning(
                "Supabase connection degraded",
                component="supabase",
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
        
        return results
        
    except Exception as e:
        error_msg = str(e)
        logger.exception("Supabase connection failed", component="supabase")
        results["errors"].append(f"Connection error: {error_msg}")
        return results
