"""
FastAPI application for Vimeo Video Chatbot - Vercel Serverless Optimized.
All imports are wrapped in try/except to prevent failures during cold starts.
"""
import os
import time
from datetime import datetime
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe

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

settings = get_settings_safe()
logger = get_logger_safe(__name__)

try:
    from app.utils.logger import cleanup_memory
except Exception:
    def cleanup_memory():
        pass

# Create FastAPI app - minimal configuration
# Only create app if FastAPI is available
if FASTAPI_AVAILABLE:
    # Enable Swagger UI only in non-production environments
    # This allows developers to test APIs locally without exposing docs in production
    try:
        is_production = settings.is_production
    except (AttributeError, Exception):
        # Fallback: check ENVIRONMENT directly
        env = getattr(settings, 'ENVIRONMENT', 'production')
        is_production = env == 'production'
    
    docs_url = "/docs" if not is_production else None
    redoc_url = "/redoc" if not is_production else None
    openapi_url = "/openapi.json" if not is_production else None
    
    app = FastAPI(
        title="PDF Knowledge Chatbot",
        description="RAG-powered chatbot for PDF document content",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
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

# Startup event - keep startup lightweight and avoid blocking on external DB checks
if app is not None and FASTAPI_AVAILABLE:
    @app.on_event("startup")
    async def startup_event():
        """Lightweight startup hook that does not block on database connectivity."""
        try:
            logger.info(
                "Startup completed without blocking database checks. "
                "Use /health/detailed or /health/database for on-demand Supabase validation."
            )
        except Exception as e:
            logger.warning("Startup hook encountered a non-blocking issue: %s", e)

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

    @app.get("/health/detailed")
    async def detailed_health_check():
        """Comprehensive health check that validates all external dependencies."""
        import os
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": getattr(settings, 'ENVIRONMENT', 'production'),
            "services": {},
            "chat_service": {}
        }
        
        overall_healthy = True
        
        # Check OpenAI
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                health_status["services"]["openai"] = {
                    "status": "available",
                    "api_key": "configured"
                }
            else:
                health_status["services"]["openai"] = {
                    "status": "unavailable",
                    "api_key": "missing"
                }
                overall_healthy = False
        except Exception as e:
            health_status["services"]["openai"] = {
                "status": "error",
                "error": str(e)
            }
            overall_healthy = False
        
        # Check Supabase
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
            if supabase_url and supabase_key:
                # Try to actually connect and test all tables
                try:
                    from app.database.supabase import test_connection
                    connection_result = test_connection()
                    
                    if connection_result.get("connected"):
                        health_status["services"]["supabase"] = {
                            "status": "available",
                            "url": "configured",
                            "key": "configured",
                            "tables": connection_result.get("tables", {}),
                            "all_tables_accessible": True
                        }
                    else:
                        health_status["services"]["supabase"] = {
                            "status": "degraded",
                            "url": "configured",
                            "key": "configured",
                            "tables": connection_result.get("tables", {}),
                            "all_tables_accessible": False,
                            "errors": connection_result.get("errors", [])
                        }
                        overall_healthy = False
                except Exception as e:
                    health_status["services"]["supabase"] = {
                        "status": "error",
                        "error": f"Connection test failed: {str(e)}"
                    }
                    overall_healthy = False
            else:
                health_status["services"]["supabase"] = {
                    "status": "unavailable",
                    "url": "missing" if not supabase_url else "configured",
                    "key": "missing" if not supabase_key else "configured"
                }
                overall_healthy = False
        except Exception as e:
            health_status["services"]["supabase"] = {
                "status": "error",
                "error": str(e)
            }
            overall_healthy = False
        
        # Vimeo service disabled - PDF-only mode
        
        # Check Chat Service Components
        try:
            from app.models.schemas import ChatRequest, ChatResponse
            health_status["chat_service"]["schemas"] = {
                "status": "available",
                "ChatRequest": ChatRequest is not None,
                "ChatResponse": ChatResponse is not None
            }
        except Exception as e:
            health_status["chat_service"]["schemas"] = {
                "status": "unavailable",
                "error": str(e)
            }
            overall_healthy = False
        
        try:
            from app.services.vector_store import load_supabase_vectorstore
            health_status["chat_service"]["vector_store"] = {
                "status": "available" if load_supabase_vectorstore else "unavailable",
                "function": "loaded" if load_supabase_vectorstore else "not_loaded"
            }
            if not load_supabase_vectorstore:
                overall_healthy = False
        except Exception as e:
            health_status["chat_service"]["vector_store"] = {
                "status": "unavailable",
                "error": str(e)
            }
            overall_healthy = False
        
        # Check router status
        health_status["routers"] = _router_status
        
        if not overall_healthy:
            health_status["status"] = "degraded"
        
        return health_status

    @app.get("/")
    async def root():
        """Backend service root endpoint."""
        return {
            "message": "PDF Knowledge Chatbot API",
            "service": "backend-only",
            "docs": "/docs" if not is_production else None,
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

    # Vimeo webhooks router disabled - PDF-only mode
    _router_status['webhooks'] = False
    
    # Vimeo video ingestion router disabled - PDF-only mode
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

    # Database connection test endpoint
    @app.get("/health/database")
    async def database_health_check():
        """Test database connection and all tables."""
        try:
            from app.database.supabase import test_connection
            connection_result = test_connection()
            
            return {
                "status": "connected" if connection_result.get("connected") else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "tables": connection_result.get("tables", {}),
                "errors": connection_result.get("errors", []),
                "message": "All tables accessible" if connection_result.get("connected") else "Some tables are not accessible"
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "message": "Database connection test failed"
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
                "note": "In Vercel, check deployment logs in dashboard for diagnostics",
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
