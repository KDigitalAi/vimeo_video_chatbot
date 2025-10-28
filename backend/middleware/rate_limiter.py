"""
Rate limiting middleware for API protection.
"""
import time
from typing import Dict
from fastapi import Request, HTTPException, status
from collections import defaultdict, deque
from backend.core.settings import settings

# In-memory rate limiting (use Redis in production)
_rate_limits: Dict[str, deque] = defaultdict(lambda: deque())

class RateLimiter:
    """Rate limiting implementation."""
    
    def __init__(self, max_requests: int = None, window_seconds: int = 60):
        self.max_requests = max_requests or settings.RATE_LIMIT_PER_MINUTE
        self.window_seconds = window_seconds
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for client IP."""
        now = time.time()
        client_requests = _rate_limits[client_ip]
        
        # Remove old requests outside window
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True

# Global rate limiter instance
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    client_ip = request.client.host
    
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    response = await call_next(request)
    return response
