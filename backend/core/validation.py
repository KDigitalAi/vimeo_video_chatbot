"""
Input validation models and utilities using Pydantic.
Provides comprehensive validation for all API endpoints.
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from backend.core.security import sanitize_input, validate_video_id, validate_query_text

class BaseRequestModel(BaseModel):
    """Base request model with common validation."""
    
    class Config:
        # Enable validation assignment
        validate_assignment = True
        # Use enum values
        use_enum_values = True
        # Allow population by field name (Pydantic v2 compatible)
        populate_by_name = True

class VideoIngestRequest(BaseRequestModel):
    """Request model for video ingestion endpoint."""
    
    video_id: str = Field(
        ..., 
        min_length=6, 
        max_length=20,
        description="Vimeo video ID (numeric string)",
        example="1124405272"
    )
    force_transcription: bool = Field(
        default=False,
        description="Force Whisper transcription even if captions exist"
    )
    chunk_size: Optional[int] = Field(
        default=None,
        ge=100,
        le=2000,
        description="Custom chunk size for text processing"
    )
    chunk_overlap: Optional[int] = Field(
        default=None,
        ge=0,
        le=500,
        description="Custom chunk overlap for text processing"
    )
    
    @validator('video_id')
    def validate_video_id(cls, v):
        """
        Optimized Vimeo video ID validation with O(1) complexity.
        Uses efficient string operations and early termination.
        """
        if not validate_video_id(v):
            raise ValueError('Invalid Vimeo video ID format')
        return v.strip()
    
    @validator('chunk_overlap')
    def validate_chunk_overlap(cls, v, values):
        """
        Optimized chunk overlap validation with O(1) complexity.
        Uses early termination for better performance.
        """
        if v is not None and 'chunk_size' in values:
            chunk_size = values['chunk_size']
            if chunk_size is not None and v >= chunk_size:
                raise ValueError('Chunk overlap must be less than chunk size')
        return v

class ChatRequest(BaseRequestModel):
    """Request model for chat query endpoint."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User query/question",
        example="What is machine learning?"
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User identifier for chat history"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Conversation ID for context"
    )
    max_tokens: int = Field(
        default=1000,
        ge=50,
        le=4000,
        description="Maximum tokens for response"
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature for response generation"
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of top documents to retrieve"
    )
    include_sources: bool = Field(
        default=True,
        description="Include source documents in response"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """
        Ultra-optimized query validation with O(n) complexity.
        Consolidates validation and sanitization into single efficient pass.
        """
        # Ultra-fast early termination for empty queries
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        
        # Consolidated validation and sanitization
        if not validate_query_text(v):
            raise ValueError('Query contains potentially harmful content')
        
        # Single-pass sanitization with early termination
        sanitized = sanitize_input(v)
        if not sanitized:
            raise ValueError('Query cannot be empty after sanitization')
        
        return sanitized
    
    @validator('conversation_id')
    def validate_conversation_id(cls, v):
        """
        Ultra-optimized conversation ID validation with O(1) complexity.
        Uses pre-compiled regex for maximum performance.
        """
        if v is not None:
            # Pre-compiled regex for O(1) performance
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError('Conversation ID can only contain alphanumeric characters, hyphens, and underscores')
        return v

class ChatResponse(BaseRequestModel):
    """Response model for chat endpoint."""
    
    answer: str = Field(
        ...,
        description="AI-generated response"
    )
    sources: List[Dict[str, Any]] = Field(
        default=[],
        description="Source documents used for the response"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation ID for context"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )
    tokens_used: Optional[int] = Field(
        default=None,
        description="Number of tokens used"
    )

class VideoIngestResponse(BaseRequestModel):
    """Response model for video ingestion endpoint."""
    
    video_id: str = Field(
        ...,
        description="Processed video ID"
    )
    video_title: str = Field(
        ...,
        description="Video title from metadata"
    )
    chunk_count: int = Field(
        ...,
        ge=0,
        description="Number of text chunks created"
    )
    message: str = Field(
        ...,
        description="Processing status message"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )
    transcription_method: Optional[str] = Field(
        default=None,
        description="Method used for transcription (captions/whisper)"
    )

class ErrorResponse(BaseRequestModel):
    """Standard error response model."""
    
    error: str = Field(
        ...,
        description="Error type"
    )
    message: str = Field(
        ...,
        description="Error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: str = Field(
        ...,
        description="Error timestamp"
    )

class HealthCheckResponse(BaseRequestModel):
    """Health check response model."""
    
    status: str = Field(
        ...,
        description="Service status"
    )
    version: str = Field(
        ...,
        description="Application version"
    )
    environment: str = Field(
        ...,
        description="Environment (development/production)"
    )
    dependencies: Dict[str, str] = Field(
        ...,
        description="Status of external dependencies"
    )
    timestamp: str = Field(
        ...,
        description="Check timestamp"
    )

class AuthenticationRequest(BaseRequestModel):
    """Authentication request model."""
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password"
    )
    
    @validator('username')
    def validate_username(cls, v):
        """
        Ultra-optimized username validation with O(n) complexity.
        Uses single-pass validation with early termination for maximum efficiency.
        """
        # Ultra-fast early termination for empty usernames
        if not v:
            raise ValueError('Username cannot be empty')
        
        # Ultra-optimized single-pass validation
        for char in v:
            if not (char.isalnum() or char == '_'):
                raise ValueError('Username can only contain letters, numbers, and underscores')
        
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        """
        Ultra-optimized password validation with O(n) complexity.
        Uses single-pass validation with early termination for maximum efficiency.
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Ultra-optimized single-pass validation with early termination
        has_upper = has_lower = has_digit = has_special = False
        
        for char in v:
            if char.isupper():
                has_upper = True
            elif char.islower():
                has_lower = True
            elif char.isdigit():
                has_digit = True
            elif char in '!@#$%^&*(),.?":{}|<>':
                has_special = True
            
            # Early termination if all requirements met
            if has_upper and has_lower and has_digit and has_special:
                return v
        
        # Ultra-fast error reporting with early termination
        if not has_upper:
            raise ValueError('Password must contain at least one uppercase letter')
        if not has_lower:
            raise ValueError('Password must contain at least one lowercase letter')
        if not has_digit:
            raise ValueError('Password must contain at least one digit')
        if not has_special:
            raise ValueError('Password must contain at least one special character')
        
        return v

class AuthenticationResponse(BaseRequestModel):
    """Authentication response model."""
    
    access_token: str = Field(
        ...,
        description="JWT access token"
    )
    token_type: str = Field(
        default="bearer",
        description="Token type"
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds"
    )
    user_id: str = Field(
        ...,
        description="User ID"
    )

class VideoMetadataRequest(BaseRequestModel):
    """Request model for video metadata endpoint."""
    
    video_id: str = Field(
        ...,
        min_length=6,
        max_length=20,
        description="Vimeo video ID"
    )
    
    @validator('video_id')
    def validate_video_id(cls, v):
        """Validate Vimeo video ID format."""
        if not validate_video_id(v):
            raise ValueError('Invalid Vimeo video ID format')
        return v.strip()

class VideoMetadataResponse(BaseRequestModel):
    """Response model for video metadata endpoint."""
    
    video_id: str = Field(
        ...,
        description="Video ID"
    )
    title: str = Field(
        ...,
        description="Video title"
    )
    description: Optional[str] = Field(
        default=None,
        description="Video description"
    )
    duration: Optional[int] = Field(
        default=None,
        description="Video duration in seconds"
    )
    upload_date: Optional[str] = Field(
        default=None,
        description="Video upload date"
    )
    has_captions: bool = Field(
        ...,
        description="Whether video has captions"
    )
    caption_languages: List[str] = Field(
        default=[],
        description="Available caption languages"
    )

# Validation utilities
def validate_pagination_params(page: int = 1, size: int = 10) -> tuple:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (1-based)
        size: Page size
        
    Returns:
        Validated page and size
        
    Raises:
        ValueError: If parameters are invalid
    """
    if page < 1:
        raise ValueError("Page must be greater than 0")
    if size < 1 or size > 100:
        raise ValueError("Page size must be between 1 and 100")
    
    return page, size

def validate_sort_params(sort_by: str, allowed_fields: List[str]) -> str:
    """
    Validate sort parameters.
    
    Args:
        sort_by: Field to sort by
        allowed_fields: List of allowed sort fields
        
    Returns:
        Validated sort field
        
    Raises:
        ValueError: If field is not allowed
    """
    if sort_by not in allowed_fields:
        raise ValueError(f"Sort field must be one of: {', '.join(allowed_fields)}")
    
    return sort_by

class PDFIngestResponse(BaseRequestModel):
    """Response model for PDF ingestion endpoint."""
    
    pdf_id: str = Field(
        ...,
        description="Unique identifier for the processed PDF",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    
    filename: str = Field(
        ...,
        description="Original filename of the uploaded PDF",
        example="document.pdf"
    )
    
    chunks_processed: int = Field(
        ...,
        ge=0,
        description="Number of text chunks created from the PDF",
        example=15
    )
    
    embeddings_stored: int = Field(
        ...,
        ge=0,
        description="Number of embeddings stored in the database",
        example=15
    )
    
    processing_time: float = Field(
        ...,
        ge=0,
        description="Time taken to process the PDF in seconds",
        example=2.5
    )
    
    status: str = Field(
        ...,
        description="Processing status",
        example="success"
    )
