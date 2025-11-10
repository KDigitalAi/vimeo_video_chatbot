"""
Configuration management with environment validation.
Serverless-safe: no file system writes at import time.
"""
import os
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get project root
@lru_cache(maxsize=1)
def get_project_root():
    """Get project root path."""
    return Path(__file__).parent.parent.parent

# Load environment variables
project_root = get_project_root()
env_path = project_root / ".env"

# Try loading .env file
try:
    load_dotenv(dotenv_path=env_path)
except Exception as e:
    logging.warning(f"Could not load .env file: {e}")

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Required API Keys
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str = Field(default="", description="Supabase service role key")
    VIMEO_ACCESS_TOKEN: str = Field(default="", description="Vimeo API access token")
    
    # AI Model Configuration
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo", description="OpenAI LLM model")
    
    # Security Configuration
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="Secret key for JWT")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration")
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000",
        description="Allowed CORS origins (comma-separated)"
    )
    
    # Environment Configuration
    ENVIRONMENT: str = Field(default="development", description="Environment")
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # Text Processing Configuration
    CHUNK_SIZE: int = Field(default=1000, description="Text chunk size")
    CHUNK_OVERLAP: int = Field(default=200, description="Text chunk overlap")
    SUPABASE_TABLE: str = Field(default="video_embeddings", description="Supabase table name")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute")
    
    # Optional Configuration
    VALIDATE_CONFIG: bool = Field(default=False, description="Validate configuration on startup")
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed = {'development', 'staging', 'production'}
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {sorted(allowed)}")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Global settings instance - serverless-safe initialization
try:
    settings = Settings()
    if settings.is_development:
        logger.info(f"Configuration loaded for {settings.ENVIRONMENT} environment")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    # Create minimal settings for serverless to avoid import failures
    settings = Settings(
        ENVIRONMENT=os.getenv("ENVIRONMENT", "production"),
        DEBUG=False
    )

