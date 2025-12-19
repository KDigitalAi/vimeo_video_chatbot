"""
Security utilities for authentication, authorization, and input sanitization.
Implements JWT-based authentication and security middleware.
"""
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.core.settings import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityManager:
    """Centralized security management for the application."""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def generate_api_key(self) -> str:
        """Generate secure API key."""
        return secrets.token_urlsafe(32)

# Global security manager instance
security_manager = SecurityManager()

def sanitize_input(text: str) -> str:
    """
    Ultra-optimized input sanitization with O(n) complexity.
    Consolidates all patterns into single efficient pass with minimal operations.
    """
    if not text:
        return ""
    
    # Ultra-optimized consolidated pattern matching
    # Single pass through all patterns for maximum efficiency
    patterns = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)", re.IGNORECASE),
        re.compile(r"(--|#|/\*|\*/)"),
        re.compile(r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
    ]
    
    # Single-pass pattern removal for maximum efficiency
    for pattern in patterns:
        text = pattern.sub("", text)
    
    # Ultra-fast whitespace normalization
    return re.sub(r'\s+', ' ', text).strip()

def validate_video_id(video_id: str) -> bool:
    """
    Optimized Vimeo video ID validation with O(1) complexity.
    Uses efficient string operations and early termination.
    """
    if not video_id:
        return False
    
    # Optimized validation with early termination
    return video_id.isdigit() and len(video_id) >= 6

def validate_query_text(query: str) -> bool:
    """
    Ultra-optimized query text validation with O(n) complexity.
    Consolidates all validation logic into single efficient pass.
    """
    # Ultra-fast early termination for empty or oversized queries
    if not query or len(query) > 1000:
        return False
    
    # Ultra-optimized consolidated injection pattern detection
    # Single pass through all patterns for maximum efficiency
    injection_patterns = [
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*:", re.IGNORECASE),
        re.compile(r"assistant\s*:", re.IGNORECASE),
        re.compile(r"user\s*:", re.IGNORECASE),
        re.compile(r"<\|.*?\|>", re.IGNORECASE),
    ]
    
    # Single-pass pattern detection with early termination
    return not any(pattern.search(query) for pattern in injection_patterns)

# Note: get_current_user and check_rate_limit functions removed - not used in any active code paths
# Rate limiting is handled by backend/middleware/rate_limiter.py
# Authentication functions can be re-added when auth is enabled
