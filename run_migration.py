#!/usr/bin/env python3
"""Script to run the Supabase migration for the match_documents function."""

import sys
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def run_migration():
    """Run the database migration to create the match_documents function."""
    try:
        from backend.core.settings import settings
        from backend.core.supabase_client import get_supabase
        
        print("Connecting to Supabase...")
        supabase = get_supabase()
        
        # Read the migration SQL
        migration_sql = """
        CREATE OR REPLACE FUNCTION public.match_documents(
          query_embedding vector(1536),
          match_count int DEFAULT 5,
          filter jsonb DEFAULT '{}'::jsonb
        )
        RETURNS TABLE (
          id uuid,
          content text,
          metadata jsonb,
          similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RETURN QUERY
          SELECT 
            ve.id,
            ve.content,
            jsonb_build_object(
              'video_id', ve.video_id,
              'video_title', ve.video_title,
              'chunk_id', ve.chunk_id,
              'timestamp_start', ve.timestamp_start,
              'timestamp_end', ve.timestamp_end
            ) as metadata,
            1 - (ve.embedding <=> query_embedding) as similarity
          FROM public.video_embeddings ve
          WHERE 1 - (ve.embedding <=> query_embedding) > 0.7
          ORDER BY ve.embedding <=> query_embedding ASC
          LIMIT LEAST(match_count, 200);
        END;
        $$;
        
        GRANT EXECUTE ON FUNCTION public.match_documents TO anon, authenticated;
        """
        
        print("Creating match_documents function...")
        result = supabase.rpc('exec_sql', {'sql': migration_sql}).execute()
        print("Migration completed successfully!")
        
        # Test the function
        print("Testing the function...")
        test_result = supabase.rpc('match_documents', {
            'query_embedding': [0.0] * 1536,  # Dummy embedding
            'match_count': 1
        }).execute()
        print(f"Function test successful! Returned {len(test_result.data)} results.")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
