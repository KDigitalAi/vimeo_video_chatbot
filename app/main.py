"""
FastAPI application for Vimeo Video Chatbot - Vercel Serverless Optimized.
All imports are wrapped in try/except to prevent failures during cold starts.
"""
import os
import time
from datetime import datetime

# Core FastAPI imports - must be at top level for Vercel
try:
    from fastapi import FastAPI, Request, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
except ImportError as e:
    raise ImportError(f"FastAPI not available: {e}")

# Safe settings import with fallback
try:
    from app.config.settings import settings
except Exception as e:
    import logging
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to load settings: {e}")
    # Minimal fallback settings
    class MinimalSettings:
        ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
        is_development = False
        is_production = True
        ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
    settings = MinimalSettings()

# Safe logger import
try:
    from app.utils.logger import logger, cleanup_memory
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    def cleanup_memory():
        pass

# Create FastAPI app - minimal configuration
app = FastAPI(
    title="Vimeo Video Knowledge Chatbot",
    description="RAG-powered chatbot for Vimeo video content",
    version="1.0.0",
    docs_url=None,  # Disable in production
    redoc_url=None,
    openapi_url=None,
)

# Add GZip middleware
try:
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
except Exception as e:
    logger.warning(f"GZipMiddleware failed: {e}")

# Add CORS middleware
try:
    origins_str = getattr(settings, 'ALLOWED_ORIGINS', '*')
    if origins_str and origins_str != '*':
        origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    else:
        origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
except Exception as e:
    logger.warning(f"CORS middleware failed: {e}")

# Security headers middleware
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers."""
    response = await call_next(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers[key] = value
    return response

# Rate limiting - optional
try:
    from app.core.middleware import rate_limit_middleware
    app.middleware("http")(rate_limit_middleware)
except Exception as e:
    logger.warning(f"Rate limiting not available: {e}")

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": {"errors": exc.errors()},
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": str(exc.detail),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unexpected error: {str(exc)}")
    error_msg = "Internal server error" if settings.is_production else str(exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Health check - must work without dependencies
@app.get("/health")
async def health_check():
    """Health check endpoint - minimal, no dependencies."""
    try:
        return {
            "status": "healthy",
            "version": "1.0.0",
            "environment": getattr(settings, 'ENVIRONMENT', 'production'),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        # Even if settings fail, return basic health
        return {
            "status": "degraded",
            "version": "1.0.0",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Vimeo Video Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "environment": getattr(settings, 'ENVIRONMENT', 'production'),
        "endpoints": {
            "health": "/health",
            "chat": "/chat/query",
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Load routers with error handling - each router loads independently
def _safe_include_router(router_name: str, router_module: str, prefix: str = None, tags: list = None):
    """Safely include a router with error handling."""
    try:
        module = __import__(router_module, fromlist=['router'])
        router = getattr(module, 'router')
        if prefix:
            app.include_router(router, prefix=prefix, tags=tags or [])
        else:
            app.include_router(router, tags=tags or [])
        logger.info(f"Successfully loaded {router_name} router")
        return True
    except Exception as e:
        logger.error(f"Failed to load {router_name} router: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Load routers - each one independently so failures don't cascade
# Wrap in try/except to ensure app can start even if routers fail
_router_status = {}

try:
    # Load chat router (most important)
    _router_status['chat'] = _safe_include_router(
        "chat",
        "app.api.routes.chat",
        prefix="/chat",
        tags=["chat"]
    )
except Exception as e:
    logger.error(f"Critical: Failed to load chat router: {e}")
    _router_status['chat'] = False

try:
    # Load other routers (optional)
    _router_status['webhooks'] = _safe_include_router(
        "webhooks",
        "app.api.routes.webhooks",
        tags=["webhooks"]
    )
except Exception as e:
    logger.warning(f"Failed to load webhooks router: {e}")
    _router_status['webhooks'] = False

try:
    _router_status['ingest'] = _safe_include_router(
        "ingest",
        "app.api.routes.ingest",
        prefix="/ingest",
        tags=["ingest"]
    )
except Exception as e:
    logger.warning(f"Failed to load ingest router: {e}")
    _router_status['ingest'] = False

try:
    _router_status['pdf'] = _safe_include_router(
        "pdf",
        "app.api.routes.pdf_ingest",
        prefix="/pdf",
        tags=["pdf"]
    )
except Exception as e:
    logger.warning(f"Failed to load pdf router: {e}")
    _router_status['pdf'] = False

# Log router status
logger.info(f"Router loading status: {_router_status}")

# Ensure at least health endpoint works
if not _router_status.get('chat', False):
    logger.error("WARNING: Chat router failed to load. /chat/query will not work.")

# Export app for Vercel - required at module level
# Vercel Python serverless functions expect 'app' to be exported
# This is the handler that Vercel will use

# Add diagnostic endpoint to help debug
@app.get("/debug/imports")
async def debug_imports():
    """Debug endpoint to check what imports succeeded."""
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "router_status": _router_status,
        "settings_loaded": hasattr(settings, 'ENVIRONMENT'),
        "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
    }
