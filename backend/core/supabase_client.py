from typing import Optional, Any
from backend.core.settings import settings
from backend.modules.vector_store_direct import get_supabase_direct

# Use the direct postgrest client as the main Supabase client
# This avoids the compatibility issues with the main Supabase library
_supabase_client: Optional[Any] = None

def get_supabase():
    """
    Ultra-optimized singleton pattern with O(1) complexity.
    Consolidates validation logic and eliminates redundant operations.
    """
    global _supabase_client
    
    if _supabase_client is None:
        # Ultra-fast consolidated validation with single pass
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
    """
    Tests if Supabase is reachable and table exists.
    """
    try:
        # Try a simple select query on your embeddings table
        resp = get_supabase().table("video_embeddings").select("*").limit(1).execute()
        print("Supabase connection OK.")
        print(f"Table returned {len(resp.data)} rows.")
        if resp.data:
            print("Sample data:", resp.data[0])
        else:
            print("Table exists but no data yet.")
    except Exception as e:
        print("Supabase connection failed:", e)


if __name__ == "__main__":
    test_connection()
