"""
Structured logging configuration for the application.
"""
import logging
import sys
from typing import Dict, Any
from backend.core.settings import settings

def setup_structured_logging() -> logging.Logger:
    """Setup structured logging with proper formatting."""
    
    # Create logger
    logger = logging.getLogger("vimeo_chatbot")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    if settings.is_development:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def log_api_request(request: Any, response: Any, processing_time: float) -> None:
    """Log API request details."""
    logger = logging.getLogger("vimeo_chatbot.api")
    
    log_data = {
        "method": request.method,
        "url": str(request.url),
        "status_code": response.status_code,
        "processing_time": processing_time,
        "client_ip": getattr(request.client, 'host', 'unknown')
    }
    
    logger.info(f"API Request: {log_data}")

def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log error with context."""
    logger = logging.getLogger("vimeo_chatbot.error")
    
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {}
    }
    
    logger.error(f"Error occurred: {error_data}", exc_info=True)
