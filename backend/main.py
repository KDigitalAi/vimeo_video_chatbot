"""
FastAPI application for Vimeo Video Chatbot.
Clean, working version without complex monitoring.
"""
import time
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from backend.core.settings import settings
from backend.core.validation import HealthCheckResponse, ErrorResponse
import logging
from backend.api.webhooks import router as webhooks_router
from backend.api.chat import router as chat_router
from backend.api.ingest import router as ingest_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Vimeo Video Knowledge Chatbot",
    description="RAG-powered chatbot for Vimeo video content with enhanced security",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

# Performance middleware - Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security middleware - Trusted hosts
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# CORS middleware - permissive for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Set to False when using wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Mount static files for frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# Routers
app.include_router(webhooks_router)
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-API-Version"] = "1.0.0"
    response.headers["X-Response-Time"] = str(time.time())
    
    return response

# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed information."""
    logger.warning(f"Validation error: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format."""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            message=exc.detail,
            details={"status_code": exc.status_code},
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {str(exc)}")
    
    # Don't expose internal errors in production
    if settings.is_production:
        message = "Internal server error"
        details = None
    else:
        message = str(exc)
        details = {"type": type(exc).__name__}
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message=message,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )

# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Comprehensive health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        dependencies={"backend": "healthy"},
        timestamp=datetime.utcnow().isoformat()
    )

# Root endpoint - serve frontend
@app.get("/")
async def root():
    """Serve the frontend chatbot interface."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    else:
        # Fallback to API info if frontend not found
        return {
            "message": "Vimeo RAG Chatbot Backend is running!",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Frontend not found. Please ensure the frontend folder exists."
        }

# Serve frontend static files - MUST be last to avoid intercepting API routes
@app.get("/{file_path:path}")
async def serve_frontend_files(file_path: str):
    """Serve frontend static files (CSS, JS, etc.)."""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    full_path = os.path.join(frontend_dir, file_path)
    
    # Security check - ensure the file is within the frontend directory
    if not os.path.abspath(full_path).startswith(os.path.abspath(frontend_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    else:
        # If file not found, serve index.html for SPA routing
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            raise HTTPException(status_code=404, detail="File not found")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting Vimeo RAG Chatbot Backend v1.0.0 in {settings.ENVIRONMENT} mode")
    try:
        allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
        logger.info(f"Allowed CORS origins: {allowed_origins}")
    except Exception:
        logger.info("Allowed CORS origins: * (development default)")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down Vimeo RAG Chatbot Backend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 