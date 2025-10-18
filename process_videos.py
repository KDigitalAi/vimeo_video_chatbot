#!/usr/bin/env python3
"""
Vimeo Video Processing Script - Production Version
Fetches videos from Vimeo, generates embeddings, and stores in Supabase
"""

import sys
import time
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def validate_environment():
    """Validate that all required environment variables are properly configured."""
    from backend.core.settings import settings
    
    print("🔍 Validating environment configuration...")
    
    # Check for placeholder values
    required_vars = {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "SUPABASE_URL": settings.SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": settings.SUPABASE_SERVICE_KEY,
        "VIMEO_ACCESS_TOKEN": settings.VIMEO_ACCESS_TOKEN
    }
    
    placeholder_patterns = ["your_", "example", "placeholder", "change-in-production"]
    
    for var_name, var_value in required_vars.items():
        if not var_value or var_value.strip() == "":
            raise ValueError(f"❌ {var_name} is not set. Please update your .env file.")
        
        for pattern in placeholder_patterns:
            if pattern in var_value.lower():
                raise ValueError(f"❌ {var_name} appears to be a placeholder value: '{var_value}'. Please provide a real API key.")
    
    print("✅ Environment validation passed - all API keys are configured")
    return True

def main():
    """Main processing function."""
    print("=" * 60)
    print("Vimeo Video Embedding Processing - Production Pipeline")
    print("=" * 60)
    
    try:
        # Early environment validation
        validate_environment()
        
        from backend.core.settings import settings
        from backend.modules.vimeo_loader import get_user_videos, get_video_metadata
        from backend.modules.transcript_manager import get_transcript_segments_from_vimeo
        from backend.modules.text_processor import make_chunks_with_metadata
        from backend.modules.vector_store_direct import store_embeddings_directly, check_duplicate_video, verify_storage
        from backend.modules.whisper_transcriber import transcribe_vimeo_audio
        
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Supabase Table: {settings.SUPABASE_TABLE}")
        print(f"Embedding Model: {settings.EMBEDDING_MODEL}")
        print()
        
        # Step 1: Fetch videos from Vimeo
        print("1. Fetching videos from Vimeo account...")
        videos = get_user_videos(limit=10)
        print(f"   Found {len(videos)} videos in Vimeo account")
        
        if not videos:
            print("   ERROR: No videos found in Vimeo account")
            return False
        
        # Step 2: Process each video
        total_processed = 0
        total_chunks = 0
        
        for i, video in enumerate(videos, 1):
            video_id = video.get('uri', '').split('/')[-1]
            video_title = video.get('name', f'Video {video_id}')
            video_duration = video.get('duration', 0)
            
            print(f"\n2.{i} Processing video: {video_title}")
            print(f"   Video ID: {video_id}")
            print(f"   Duration: {video_duration}s")
            
            # Check if already processed
            if check_duplicate_video(video_id):
                print(f"   SKIP: Video {video_id} already exists in database")
                continue
            
            try:
                # Get video metadata
                metadata = get_video_metadata(video_id)
                print(f"   Metadata: Retrieved")
                
                # Try to get captions/transcript
                segments = get_transcript_segments_from_vimeo(video_id)
                transcription_method = "captions"
                
                if not segments:
                    print(f"   No captions found, trying Whisper transcription...")
                    try:
                        segments = transcribe_vimeo_audio(video_id)
                        transcription_method = "whisper"
                        print(f"   Whisper transcription: {'SUCCESS' if segments else 'FAILED'}")
                    except Exception as e:
                        print(f"   Whisper transcription failed: {e}")
                        continue
                else:
                    print(f"   Captions found: {len(segments)} segments")
                
                if not segments:
                    print(f"   ERROR: No transcript available for video {video_id}")
                    continue
                
                # Create chunks
                chunks = make_chunks_with_metadata(segments, video_id, video_title)
                print(f"   Chunks created: {len(chunks)}")
                
                if not chunks:
                    print(f"   ERROR: No chunks created for video {video_id}")
                    continue
                
                # Store embeddings in Supabase
                print(f"   Storing embeddings in Supabase...")
                stored_count = store_embeddings_directly(chunks)
                
                if stored_count > 0:
                    print(f"   SUCCESS: Stored {stored_count} embeddings for video {video_id}")
                    total_processed += 1
                    total_chunks += stored_count
                else:
                    print(f"   ERROR: Failed to store embeddings for video {video_id}")
                
            except Exception as e:
                print(f"   ERROR: Failed to process video {video_id}: {e}")
                continue
        
        # Step 3: Verify storage
        print(f"\n3. Verifying storage...")
        verify_storage()
        
        # Summary
        print(f"\n" + "=" * 60)
        print(f"PROCESSING COMPLETE")
        print(f"=" * 60)
        print(f"Videos processed: {total_processed}")
        print(f"Total chunks stored: {total_chunks}")
        
        if total_processed > 0:
            print(f"\nSUCCESS: All Vimeo videos successfully embedded and stored in Supabase!")
            return True
        else:
            print(f"\nERROR: No videos were processed successfully")
            return False
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
