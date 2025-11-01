"""
Configuration management with environment validation and security improvements.
Follows 12-Factor App principles for configuration management.
"""
import os
import logging
import pathlib
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cache the project root path to avoid repeated calculations
@lru_cache(maxsize=1)
def get_project_root():
    """Get project root path with caching for O(1) access."""
    return pathlib.Path(__file__).parent.parent.parent

# Load environment variables with optimized path resolution and encoding fallback
project_root = get_project_root()
env_path = project_root / ".env"

# Try loading with different encodings to handle BOM and encoding issues
try:
    load_dotenv(dotenv_path=env_path)
except UnicodeDecodeError:
    logger.warning("Failed to load .env with default encoding, trying UTF-8-sig")
    try:
        # Try with UTF-8-sig to handle BOM
        load_dotenv(dotenv_path=env_path, encoding="utf-8-sig")
    except Exception as e:
        logger.error(f"Failed to load .env file: {e}")
        # Create a minimal .env file as fallback
        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("# Minimal .env file created as fallback\n")
                f.write("ENVIRONMENT=development\n")
                f.write("DEBUG=true\n")
            load_dotenv(dotenv_path=env_path)
        except Exception as fallback_error:
            logger.error(f"Failed to create fallback .env: {fallback_error}")

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings with validation and security defaults."""
    
    # Required API Keys - will raise validation error if missing in production
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for embeddings and LLM")
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str = Field(default="", description="Supabase service role key")
    VIMEO_ACCESS_TOKEN: str = Field(default="", description="Vimeo API access token")
    
    # AI Model Configuration
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo", description="OpenAI LLM model for chat")
    
    # Security Configuration
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="Secret key for JWT tokens")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration time")
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000",
        description="Allowed CORS origins (comma-separated)"
    )
    
    # Environment Configuration
    ENVIRONMENT: str = Field(default="development", description="Environment (development/production)")
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # Text Processing Configuration
    CHUNK_SIZE: int = Field(default=1000, description="Text chunk size for processing")
    CHUNK_OVERLAP: int = Field(default=200, description="Text chunk overlap")
    SUPABASE_TABLE: str = Field(default="video_embeddings", description="Supabase table name")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute")
    
    # Optional Configuration
    VALIDATE_CONFIG: bool = Field(default=False, description="Validate configuration on startup")
    
    @field_validator('OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'VIMEO_ACCESS_TOKEN')
    @classmethod
    def validate_required_keys(cls, v, info):
        """
        Ultra-optimized validation with O(1) complexity and minimal operations.
        Consolidates all validation logic into a single efficient function.
        """
        # Ultra-fast early termination for empty values
        if not v or not v.strip():
            # Single O(1) lookup for development mode
            if hasattr(info, 'data') and info.data.get('ENVIRONMENT') == 'development':
                return v
            raise ValueError("Required API key cannot be empty")
        
        v = v.strip()
        field_name = str(info.field_name)
        
        # Consolidated validation with single pass
        if "OPENAI_API_KEY" in field_name:
            if not v.startswith("sk-"):
                raise ValueError("OpenAI API key should start with 'sk-'")
        elif "SUPABASE_URL" in field_name:
            if not v.startswith("https://") or "supabase.co" not in v:
                raise ValueError("Supabase URL should be a valid https:// URL ending with supabase.co")
        
        # Optimized placeholder detection with single pass
        v_lower = v.lower()
        if any(pattern in v_lower for pattern in ("your_", "example", "placeholder", "change-in-production", "your-", "replace-with", "add-your", "enter-your")):
            raise ValueError(f"API key appears to be a placeholder value. Please provide a real API key instead of: {v}")
        
        return v
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        """
        Ultra-optimized environment validation with O(1) complexity.
        Uses frozenset for O(1) lookup performance.
        """
        # Pre-defined frozenset for O(1) lookup
        allowed_envs = frozenset(['development', 'staging', 'production'])
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of: {sorted(allowed_envs)}")
        return v
    
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Allow extra environment variables to be ignored
    )

# Global settings instance
try:
    settings = Settings()
    logger.info(f"Configuration loaded successfully for {settings.ENVIRONMENT} environment")
    logger.info(f"Environment file loaded from: {env_path}")
    
    # Log environment variable status (without exposing secrets)
    logger.info(f"OpenAI API Key configured: {'Yes' if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith('your_') else 'No'}")
    logger.info(f"Supabase URL configured: {'Yes' if settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith('your_') else 'No'}")
    logger.info(f"Supabase Service Key configured: {'Yes' if settings.SUPABASE_SERVICE_KEY and not settings.SUPABASE_SERVICE_KEY.startswith('your_') else 'No'}")
    logger.info(f"Vimeo Access Token configured: {'Yes' if settings.VIMEO_ACCESS_TOKEN and not settings.VIMEO_ACCESS_TOKEN.startswith('your_') else 'No'}")
    
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise SystemExit(f"Configuration error: {e}")

# Validate critical settings on startup
def validate_configuration():
    """Validate critical configuration settings."""
    # Skip validation in development mode
    if settings.ENVIRONMENT == "development":
        logger.info("Skipping configuration validation in development mode")
        return
    
    required_settings = [
        ("OPENAI_API_KEY", settings.OPENAI_API_KEY),
        ("SUPABASE_URL", settings.SUPABASE_URL),
        ("SUPABASE_SERVICE_KEY", settings.SUPABASE_SERVICE_KEY),
        ("VIMEO_ACCESS_TOKEN", settings.VIMEO_ACCESS_TOKEN),
    ]
    
    missing_settings = []
    for name, value in required_settings:
        if not value or value.strip() == "":
            missing_settings.append(name)
    
    if missing_settings:
        error_msg = f"Missing required environment variables: {', '.join(missing_settings)}"
        logger.error(error_msg)
        raise SystemExit(error_msg)
    
    logger.info("Configuration validation passed")

# Run validation on import (only in production or when explicitly called)
if os.getenv("VALIDATE_CONFIG", "false").lower() == "true":
    validate_configuration()