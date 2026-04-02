"""
Input validation models and utilities using Pydantic.
Provides comprehensive validation for all API endpoints.
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Safe import of security functions with fallbacks
try:
    from app.config.security import sanitize_input, validate_query_text
except ImportError:
    # Fallback implementations if security module fails to import
    def sanitize_input(text: str) -> str:
        """Fallback sanitize function."""
        if not text:
            return ""
        return ' '.join(text.split())
    
    def validate_query_text(text: str) -> bool:
        """Fallback query text validation."""
        return bool(text and len(text.strip()) > 0)

class BaseRequestModel(BaseModel):
    """Base request model with common validation."""

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        populate_by_name=True,
    )

# VideoIngestRequest removed - PDF-only mode

class ChatRequest(BaseRequestModel):
    """Request model for chat query endpoint."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User query/question",
        json_schema_extra={"example": "What is machine learning?"},
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
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and sanitize query text."""
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        
        if not validate_query_text(v):
            raise ValueError('Query contains potentially harmful content')
        
        sanitized = sanitize_input(v)
        if not sanitized:
            raise ValueError('Query cannot be empty after sanitization')
        
        return sanitized

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate conversation ID format."""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError('Conversation ID can only contain alphanumeric characters, hyphens, and underscores')
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize user identifiers."""
        if v is None:
            return v
        normalized = v.strip()
        if not normalized:
            raise ValueError('User ID cannot be empty')
        return normalized


class ChatQueryPayload(BaseRequestModel):
    """Envelope model for chat query requests."""

    request: ChatRequest


class SessionEndRequest(BaseRequestModel):
    """Request model for legacy session end operations."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Session identifier to end",
    )

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

# VideoIngestResponse removed - PDF-only mode

class PDFIngestResponse(BaseRequestModel):
    """Response model for PDF ingestion endpoint."""
    
    pdf_id: str = Field(
        ...,
        description="Unique identifier for the processed PDF",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    
    filename: str = Field(
        ...,
        description="Original filename of the uploaded PDF",
        json_schema_extra={"example": "document.pdf"},
    )
    
    chunks_processed: int = Field(
        ...,
        ge=0,
        description="Number of text chunks created from the PDF",
        json_schema_extra={"example": 15},
    )
    
    embeddings_stored: int = Field(
        ...,
        ge=0,
        description="Number of embeddings stored in the database",
        json_schema_extra={"example": 15},
    )
    
    processing_time: float = Field(
        ...,
        ge=0,
        description="Time taken to process the PDF in seconds",
        json_schema_extra={"example": 2.5},
    )
    
    status: str = Field(
        ...,
        description="Processing status",
        json_schema_extra={"example": "success"},
    )
