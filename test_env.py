#!/usr/bin/env python3
"""Test script to verify environment variables are loaded correctly."""

try:
    from backend.core.settings import settings
    print("Environment loaded successfully")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"OpenAI Key configured: {bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith('your_'))}")
    print(f"Supabase URL configured: {bool(settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith('your_'))}")
    print(f"Supabase Service Key configured: {bool(settings.SUPABASE_SERVICE_KEY and not settings.SUPABASE_SERVICE_KEY.startswith('your_'))}")
    print(f"Vimeo Access Token configured: {bool(settings.VIMEO_ACCESS_TOKEN and not settings.VIMEO_ACCESS_TOKEN.startswith('your_'))}")
    print(f"Debug mode: {settings.DEBUG}")
    print(f"Chunk size: {settings.CHUNK_SIZE}")
    print(f"Supabase table: {settings.SUPABASE_TABLE}")
except Exception as e:
    print(f"Error loading environment: {e}")
    import traceback
    traceback.print_exc()
