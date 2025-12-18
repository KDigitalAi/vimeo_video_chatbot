"""
Security utilities for input validation and sanitization.
"""
import re
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Security scheme
security = HTTPBearer(auto_error=False)

def sanitize_input(text: str) -> str:
    """
    Sanitize user input by removing potentially harmful characters.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes and control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    return text.strip()

# validate_video_id function removed - PDF-only mode

def validate_query_text(query: str) -> bool:
    """
    Validate query text for potentially harmful content.
    
    Args:
        query: Query text to validate
        
    Returns:
        True if valid, False if potentially harmful
    """
    if not query or not query.strip():
        return False
    
    # Check for SQL injection patterns
    sql_patterns = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)',
        r'(\b(UNION|OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\'|\"|;|--|\/\*|\*\/)',
    ]
    
    query_upper = query.upper()
    for pattern in sql_patterns:
        if re.search(pattern, query_upper, re.IGNORECASE):
            return False
    
    # Check for script injection patterns
    script_patterns = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onload=',
    ]
    
    for pattern in script_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return False
    
    # Check length (reasonable limit)
    if len(query) > 5000:
        return False
    
    return True

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Get current authenticated user from JWT token.
    Currently returns None (authentication disabled).
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User information or None if not authenticated
    """
    # Authentication is currently disabled
    # Uncomment and implement when needed
    # if not credentials:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Not authenticated"
    #     )
    # 
    # # Verify JWT token here
    # # Return user info
    return None

# Alias for backward compatibility
HTTPAuthorizationCredentials = HTTPAuthorizationCredentials

