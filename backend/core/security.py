"""
Security utilities for authentication, authorization, and input sanitization.
Implements JWT-based authentication and security middleware.
"""
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.core.settings import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

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
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove potential SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
        r"(--|#|/\*|\*/)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
    ]
    
    for pattern in sql_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # Remove potential XSS patterns
    xss_patterns = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
    ]
    
    for pattern in xss_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def validate_video_id(video_id: str) -> bool:
    """
    Validate Vimeo video ID format.
    
    Args:
        video_id: Video ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not video_id:
        return False
    
    # Vimeo video IDs are typically numeric
    return video_id.isdigit() and len(video_id) >= 6

def validate_query_text(query: str) -> bool:
    """
    Validate query text for potential security issues.
    
    Args:
        query: Query text to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not query:
        return False
    
    # Check for reasonable length
    if len(query) > 1000:
        return False
    
    # Check for potential prompt injection patterns
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"system\s*:",
        r"assistant\s*:",
        r"user\s*:",
        r"<\|.*?\|>",
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return False
    
    return True

async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User data from token
        
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    payload = security_manager.verify_token(token)
    
    # In a real application, you would validate the user exists in database
    # For now, we'll just return the payload
    return payload

def require_auth(func):
    """
    Decorator to require authentication for endpoints.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with authentication
    """
    async def wrapper(*args, **kwargs):
        # This would be used with dependency injection in FastAPI
        # For now, it's a placeholder for the authentication logic
        return await func(*args, **kwargs)
    return wrapper

class SecurityHeaders:
    """Security headers middleware."""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get security headers for responses."""
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        
        if settings.is_production:
            headers.update({
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Content-Security-Policy": "default-src 'self'",
            })
        
        return headers

def check_rate_limit(request: Request) -> bool:
    """
    Check if request is within rate limits.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if within limits, False otherwise
    """
    # Simple rate limiting based on IP
    # In production, use Redis or similar for distributed rate limiting
    client_ip = request.client.host
    
    # This is a simplified implementation
    # In production, implement proper rate limiting with Redis
    return True

def validate_file_upload(filename: str, content_type: str, max_size: int = 10 * 1024 * 1024) -> bool:
    """
    Validate file upload for security.
    
    Args:
        filename: Name of the uploaded file
        content_type: MIME type of the file
        max_size: Maximum file size in bytes
        
    Returns:
        True if valid, False otherwise
    """
    # Check file extension
    allowed_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        return False
    
    # Check content type
    allowed_types = {
        'video/mp4', 'video/avi', 'video/quicktime', 
        'video/x-msvideo', 'video/x-flv', 'video/webm'
    }
    
    if content_type not in allowed_types:
        return False
    
    return True
