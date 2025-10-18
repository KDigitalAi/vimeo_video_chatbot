"""
Configuration management with environment validation and security improvements.
Follows 12-Factor App principles for configuration management.
"""
import os
import logging
from typing import Optional, List
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Load environment variables from project root
import pathlib
project_root = pathlib.Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

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
        """Validate that required API keys are provided and are not placeholder values."""
        # Skip validation in development mode if keys are empty
        if not v or v.strip() == "":
            # Check if we're in development mode
            if hasattr(info, 'data') and info.data.get('ENVIRONMENT') == 'development':
                return v  # Allow empty keys in development
            raise ValueError("Required API key cannot be empty")
        
        v = v.strip()
        
        # Check for placeholder values
        placeholder_patterns = [
            "your_", "example", "placeholder", "change-in-production", 
            "your-", "replace-with", "add-your", "enter-your"
        ]
        
        for pattern in placeholder_patterns:
            if pattern in v.lower():
                raise ValueError(f"API key appears to be a placeholder value. Please provide a real API key instead of: {v}")
        
        # Additional validation for specific keys
        if "OPENAI_API_KEY" in str(info.field_name):
            if not v.startswith("sk-"):
                raise ValueError("OpenAI API key should start with 'sk-'")
        
        if "SUPABASE_URL" in str(info.field_name):
            if not v.startswith("https://") or "supabase.co" not in v:
                raise ValueError("Supabase URL should be a valid https:// URL ending with supabase.co")
        
        return v
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed_envs = ['development', 'staging', 'production']
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of: {allowed_envs}")
        return v
    
    # @field_validator('ALLOWED_ORIGINS', mode='before')
    # @classmethod
    # def parse_origins(cls, v):
    #     """Parse CORS origins from string or list."""
    #     if isinstance(v, str):
    #         return [origin.strip() for origin in v.split(',') if origin.strip()]
    #     return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

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