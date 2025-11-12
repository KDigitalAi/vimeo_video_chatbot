"""
FastAPI application for Vimeo Video Chatbot - Vercel Serverless Optimized.
All imports are wrapped in try/except to prevent failures during cold starts.
"""
import os
import time
from datetime import datetime

# Core FastAPI imports - must be at top level for Vercel
# DO NOT raise exceptions here - let api/index.py handle them
try:
    from fastapi import FastAPI, Request, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    FASTAPI_AVAILABLE = True
except ImportError as e:
    # Log but don't raise - api/index.py will handle this
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"FastAPI not available: {e}")
    FASTAPI_AVAILABLE = False
    # Set dummy values to prevent NameError
    FastAPI = None
    Request = None
    HTTPException = None
    status = None
    CORSMiddleware = None
    GZipMiddleware = None
    JSONResponse = None
    RequestValidationError = None

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
# Only create app if FastAPI is available
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Vimeo Video Knowledge Chatbot",
        description="RAG-powered chatbot for Vimeo video content",
        version="1.0.0",
        docs_url=None,  # Disable in production
        redoc_url=None,
        openapi_url=None,
    )
else:
    # Create a dummy app object to prevent NameError
    # api/index.py will handle the actual error
    app = None

# Add GZip middleware
if app is not None and FASTAPI_AVAILABLE:
    try:
        app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
    except Exception as e:
        logger.warning(f"GZipMiddleware failed: {e}")

# Add CORS middleware
if app is not None and FASTAPI_AVAILABLE:
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
if app is not None and FASTAPI_AVAILABLE:
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
if app is not None and FASTAPI_AVAILABLE:
    try:
        from app.core.middleware import rate_limit_middleware
        app.middleware("http")(rate_limit_middleware)
    except Exception as e:
        logger.warning(f"Rate limiting not available: {e}")

# Exception handlers
if app is not None and FASTAPI_AVAILABLE:
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
if app is not None and FASTAPI_AVAILABLE:
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
    if app is None or not FASTAPI_AVAILABLE:
        logger.error(f"Cannot load {router_name} router: FastAPI app is not available")
        return False
    
    try:
        logger.info(f"Attempting to load {router_name} router from {router_module}")
        module = __import__(router_module, fromlist=['router'])
        logger.info(f"Successfully imported module {router_module}")
        
        if not hasattr(module, 'router'):
            logger.error(f"Module {router_module} does not have 'router' attribute")
            return False
            
        router = getattr(module, 'router')
        logger.info(f"Found router object: {type(router)}")
        
        if prefix:
            app.include_router(router, prefix=prefix, tags=tags or [])
            logger.info(f"Successfully registered {router_name} router with prefix {prefix}")
        else:
            app.include_router(router, tags=tags or [])
            logger.info(f"Successfully registered {router_name} router without prefix")
        
        return True
    except ImportError as e:
        logger.error(f"ImportError loading {router_name} router from {router_module}: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return False
    except AttributeError as e:
        logger.error(f"AttributeError loading {router_name} router: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error loading {router_name} router: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return False

# Initialize router status - accessible everywhere
_router_status = {}

# Load routers only if app is available
if app is not None and FASTAPI_AVAILABLE:
    # Load routers - each one independently so failures don't cascade
    # Wrap in try/except to ensure app can start even if routers fail

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

    # Add diagnostic endpoint to help debug router loading
    @app.get("/debug/routers")
    async def debug_routers():
        """Debug endpoint to check router loading status - works in production."""
        try:
            # Get all registered routes
            routes_info = []
            for route in app.routes:
                route_info = {
                    "path": route.path,
                    "name": getattr(route, 'name', 'unknown')
                }
                # Get methods if available
                if hasattr(route, 'methods'):
                    route_info["methods"] = list(route.methods)
                routes_info.append(route_info)
            
            # Check environment variables (without exposing values)
            import os
            env_vars_status = {
                "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "missing",
                "SUPABASE_URL": "set" if os.getenv("SUPABASE_URL") else "missing",
                "SUPABASE_SERVICE_KEY": "set" if os.getenv("SUPABASE_SERVICE_KEY") else "missing",
                "VIMEO_ACCESS_TOKEN": "set" if os.getenv("VIMEO_ACCESS_TOKEN") else "missing",
                "ENVIRONMENT": os.getenv("ENVIRONMENT", "not_set"),
                "VERCEL": os.getenv("VERCEL", "not_set"),
                "VERCEL_ENV": os.getenv("VERCEL_ENV", "not_set")
            }
            
            # Check for import errors
            import sys
            import_errors = []
            for module_name in sys.modules:
                if module_name.startswith('app.'):
                    try:
                        module = sys.modules[module_name]
                        # Check if module has any obvious errors
                        if hasattr(module, '__file__') and module.__file__:
                            pass  # Module loaded successfully
                    except Exception as e:
                        import_errors.append(f"{module_name}: {str(e)}")
            
            return {
                "router_status": _router_status,
                "settings_loaded": hasattr(settings, 'ENVIRONMENT'),
                "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
                "fastapi_available": FASTAPI_AVAILABLE,
                "app_created": app is not None,
                "available_routes": routes_info,
                "total_routes": len(routes_info),
                "environment_variables": env_vars_status,
                "python_version": sys.version,
                "import_errors": import_errors[:10]  # Limit to first 10 errors
            }
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "router_status": _router_status,
                "environment": getattr(settings, 'ENVIRONMENT', 'unknown') if 'settings' in globals() else 'unknown'
            }
    
    # Add logs endpoint (Vercel-compatible)
    @app.get("/_logs")
    async def get_logs():
        """Get recent application logs - Vercel compatible endpoint."""
        try:
            import logging
            import sys
            
            # Collect log records from memory (if available)
            log_records = []
            
            # Check if there's a file handler we can read from
            logger_handlers = logger.handlers if hasattr(logger, 'handlers') else []
            for handler in logger_handlers:
                if hasattr(handler, 'stream') and hasattr(handler.stream, 'getvalue'):
                    # StringIO handler - get its contents
                    log_content = handler.stream.getvalue()
                    if log_content:
                        log_records = log_content.split('\n')[-50:]  # Last 50 lines
                        break
            
            return {
                "status": "ok",
                "message": "Logs endpoint active",
                "note": "In Vercel, check deployment logs in dashboard or use /debug/routers for diagnostics",
                "log_level": logging.getLevelName(logger.level) if hasattr(logger, 'level') else "unknown",
                "handlers": [type(h).__name__ for h in logger_handlers],
                "recent_logs": log_records[-20:] if log_records else ["No in-memory logs available. Check Vercel deployment logs."]
            }
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "message": "Failed to retrieve logs"
            }
