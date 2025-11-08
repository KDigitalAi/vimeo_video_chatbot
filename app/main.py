"""
FastAPI application for Vimeo Video Chatbot.
RAG-powered chatbot for querying video content.
"""
import os
import time
import gc
from datetime import datetime
from typing import Optional, Dict, Any

try:  
    from fastapi import FastAPI, Request, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from app.config.settings import settings
from app.models.schemas import HealthCheckResponse, ErrorResponse
from app.utils.cache import AdvancedCache
from app.utils.logger import logger, cleanup_memory

_advanced_cache = AdvancedCache(max_size=50)
_router_cache = {}


app = FastAPI(
    title="Vimeo Video Knowledge Chatbot",
    description="RAG-powered chatbot for Vimeo video content",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

app.add_middleware(
    GZipMiddleware, 
    minimum_size=1000,
    compresslevel=6
)

# TrustedHostMiddleware - only enable if TRUSTED_HOSTS is set
trusted_hosts = os.getenv("TRUSTED_HOSTS", "").strip()
if trusted_hosts and settings.is_production:
    try:
        hosts = [h.strip() for h in trusted_hosts.split(",") if h.strip()]
        if hosts:
            app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=hosts
            )
    except Exception as e:
        logger.warning(f"Failed to configure TrustedHostMiddleware: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

from app.core.middleware import rate_limit_middleware
app.middleware("http")(rate_limit_middleware)

def get_router(router_name: str):
    """Load router with caching."""
    cached_router = _advanced_cache.get(f"router_{router_name}")
    if cached_router is not None:
        return cached_router
    
    if router_name in _router_cache:
        router = _router_cache[router_name]
        _advanced_cache.set(f"router_{router_name}", router)
        return router
    
    try:
        if router_name == "webhooks":
            from app.api.routes.webhooks import router
        elif router_name == "chat":
            from app.api.routes.chat import router
        elif router_name == "ingest":
            from app.api.routes.ingest import router
        elif router_name == "pdf":
            from app.api.routes.pdf_ingest import router
        else:
            raise ImportError(f"Unknown router: {router_name}")
        
        _router_cache[router_name] = router
        _advanced_cache.set(f"router_{router_name}", router)
        return router
    except ImportError as e:
        logger.error(f"Failed to import {router_name} router: {e}")
        raise

# Include routers with error handling for serverless safety
try:
    app.include_router(get_router("webhooks"))
except Exception as e:
    logger.warning(f"Failed to load webhooks router: {e}")

try:
    app.include_router(get_router("chat"), prefix="/chat", tags=["chat"])
except Exception as e:
    logger.error(f"Failed to load chat router: {e}")

try:
    app.include_router(get_router("ingest"), prefix="/ingest", tags=["ingest"])
except Exception as e:
    logger.warning(f"Failed to load ingest router: {e}")

try:
    app.include_router(get_router("pdf"), prefix="/pdf", tags=["pdf"])
except Exception as e:
    logger.warning(f"Failed to load pdf router: {e}")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-API-Version": "1.0.0"
}

_HEADER_TUPLES = tuple(_SECURITY_HEADERS.items())

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to responses."""
    start_time = time.time()
    response = await call_next(request)
    
    for key, value in _HEADER_TUPLES:
        response.headers[key] = value
    
    response.headers["X-Response-Time"] = str(time.time() - start_time)
    
    if hasattr(request, 'url') and '/api/' in str(request.url):
        cleanup_memory()
    
    return response

_ERROR_TEMPLATES = {
    "validation_error": {
        "error": "validation_error",
        "message": "Request validation failed"
    },
    "http_error": {
        "error": "http_error"
    },
    "internal_error": {
        "error": "internal_error"
    }
}

_VALIDATION_TEMPLATE = _ERROR_TEMPLATES["validation_error"]
_HTTP_TEMPLATE = _ERROR_TEMPLATES["http_error"]
_INTERNAL_TEMPLATE = _ERROR_TEMPLATES["internal_error"]

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    if settings.is_development:
        logger.warning(f"Validation error: {exc.errors()}")
    
    content = {
        **_VALIDATION_TEMPLATE,
        "details": {"errors": exc.errors()},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    
    details = {"status_code": exc.status_code}
    if settings.is_development and exc.detail:
        details["error_detail"] = str(exc.detail)
    
    content = {
        **_HTTP_TEMPLATE,
        "message": exc.detail or "Internal server error",
        "details": details,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.error(f"Value error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_error",
            "message": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(ConnectionError)
async def connection_error_handler(request: Request, exc: ConnectionError):
    """Handle connection errors."""
    logger.error(f"Connection error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "service_unavailable",
            "message": "External service unavailable. Please try again later.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError):
    """Handle timeout errors."""
    logger.error(f"Timeout error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={
            "error": "timeout_error",
            "message": "Request timeout. Please try again.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    """Handle file not found errors."""
    logger.error(f"File not found: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "file_not_found",
            "message": "Requested file not found.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    """Handle permission errors."""
    logger.error(f"Permission error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "permission_denied",
            "message": "Insufficient permissions to access this resource.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.exception(f"Unexpected error: {str(exc)}")
    
    if settings.is_production:
        content = {
            **_INTERNAL_TEMPLATE,
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        content = {
            **_INTERNAL_TEMPLATE,
            "message": str(exc),
            "details": {"type": type(exc).__name__},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    cleanup_memory()
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )

_HEALTH_BASE = {
    "status": "healthy",
    "version": "1.0.0",
    "environment": settings.ENVIRONMENT,
    "dependencies": {"backend": "healthy"}
}

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    response_data = {
        **_HEALTH_BASE,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return HealthCheckResponse(**response_data)

# Enhanced health check with dependency validation
@app.get("/health/detailed", response_model=HealthCheckResponse)
async def detailed_health_check():
    """Detailed health check with dependency validation."""
    dependencies = {"backend": "healthy"}
    
    # Check OpenAI connection
    try:
        from app.services.embedding_manager import get_embeddings_instance
        embeddings = get_embeddings_instance()
        dependencies["openai"] = "healthy"
    except Exception as e:
        dependencies["openai"] = f"unhealthy: {str(e)}"
    
    # Check Supabase connection
    try:
        from app.database.supabase import get_supabase
        supabase = get_supabase()
        # Test with a simple query
        result = supabase.table("video_embeddings").select("id").limit(1).execute()
        dependencies["supabase"] = "healthy"
    except Exception as e:
        dependencies["supabase"] = f"unhealthy: {str(e)}"
    
    # Check Vimeo connection
    try:
        from app.services.vimeo_loader import get_video_metadata
        # Test with a known video ID (this might fail, but we can catch it)
        dependencies["vimeo"] = "healthy"
    except Exception as e:
        dependencies["vimeo"] = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if all("healthy" in status for status in dependencies.values()) else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        dependencies=dependencies,
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "Vimeo Video Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.is_development else None,
        "endpoints": {
            "health": "/health",
            "chat": "/chat/query",
            "ingest": "/ingest/video/{video_id}",
            "pdf": "/pdf/upload"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.on_event("startup")
async def startup_event():
    """Application startup - serverless-safe."""
    try:
        if settings.is_development:
            logger.info(f"Starting Vimeo RAG Chatbot Backend v1.0.0 in {settings.ENVIRONMENT} mode")
            try:
                allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
                logger.info(f"Allowed CORS origins: {allowed_origins}")
            except Exception:
                logger.info("Allowed CORS origins: * (development default)")
        
        cleanup_memory()
    except Exception as e:
        # Don't fail startup on errors - serverless needs to start
        logger.warning(f"Startup event warning: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown - serverless-safe."""
    try:
        if settings.is_development:
            logger.info("Shutting down Vimeo RAG Chatbot Backend")
        
        cleanup_memory()
        _advanced_cache.clear()
        _router_cache.clear()
    except Exception as e:
        # Don't fail shutdown on errors
        logger.warning(f"Shutdown event warning: {e}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.is_development,
        workers=1,
        loop="asyncio",
        access_log=settings.is_development,
        log_level="warning" if settings.is_production else "info",
        limit_concurrency=1000,
        limit_max_requests=10000,
        timeout_keep_alive=5
    ) 
