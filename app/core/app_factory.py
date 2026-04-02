"""Application factory and bootstrap composition."""
from __future__ import annotations

from contextlib import asynccontextmanager
import time
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.core.exceptions import AppError
from app.core.request_context import reset_request_context, set_request_context
from app.utils.runtime_helpers import get_logger_safe

logger = get_logger_safe(__name__)

CANONICAL_API_NOTE = (
    "Primary HTTP contract is under `/chat/*`, `/pdf/*`, `/health`, and `/ops/*`. "
    "`/api/v1/*` mirrors exist for compatibility but are omitted from OpenAPI."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup/shutdown lifecycle."""
    logger.info(
        "Startup completed without blocking database checks. "
        "Use /ops/health/database for on-demand Supabase validation."
    )
    yield


def _is_production() -> bool:
    try:
        return settings.is_production
    except Exception:
        return getattr(settings, "ENVIRONMENT", "production") == "production"


def _register_middleware(app: FastAPI) -> None:
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

    origins_str = getattr(settings, "ALLOWED_ORIGINS", "*")
    origins = (
        [origin.strip() for origin in origins_str.split(",") if origin.strip()]
        if origins_str and origins_str != "*"
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in security_headers.items():
            response.headers[key] = value
        return response

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        user_id, session_id = await _extract_request_identity(request)
        tokens = set_request_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            path=request.url.path,
            method=request.method,
        )
        request.state.request_id = request_id
        request.state.user_id = user_id
        request.state.session_id = session_id

        logger.info(
            "Request started",
            component="http",
            request_path=request.url.path,
            request_method=request.method,
        )
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "Request failed",
                component="http",
                request_path=request.url.path,
                request_method=request.method,
                duration_ms=duration_ms,
            )
            reset_request_context(tokens)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "Request completed",
            component="http",
            request_path=request.url.path,
            request_method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        reset_request_context(tokens)
        return response

    try:
        from app.core.middleware import rate_limit_middleware

        app.middleware("http")(rate_limit_middleware)
    except Exception as exc:
        logger.warning("Rate limiting not available: %s", exc)


async def _extract_request_identity(request: Request) -> tuple[str | None, str | None]:
    """Extract user and session identifiers without re-parsing request bodies."""
    user_id = request.headers.get("X-User-Id") or request.query_params.get("user_id")
    session_id = request.headers.get("X-Session-Id") or request.query_params.get("session_id")
    return user_id, session_id


def _register_exception_handlers(app: FastAPI) -> None:
    def _error_response(
        *,
        request: Request,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> JSONResponse:
        """Build the standardized API error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "code": code,
                "message": message,
                "details": details or {},
                "timestamp": datetime.now(UTC).isoformat(),
                "path": str(request.url.path),
                "method": request.method,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return _error_response(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError):
        logger.exception("Application error: %s", exc)
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        details = {}
        message = str(exc.detail)
        code = "http_error"
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", code)
            message = exc.detail.get("message", message)
            details = exc.detail.get("details", {})
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=code,
            message=message,
            details=details,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception("Unexpected error: %s", exc)
        error_msg = "Internal server error" if _is_production() else str(exc)
        return _error_response(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message=error_msg,
        )


def _build_database_health_payload() -> tuple[dict, int]:
    """Build the database health payload and status code."""
    try:
        from app.database.supabase import test_connection

        connection_result = test_connection()
        connected = connection_result.get("connected")
        return ({
            "status": "healthy" if connected else "degraded",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Database connection healthy" if connected else "Database unavailable",
        }, status.HTTP_200_OK if connected else status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as exc:
        logger.exception("Database health check failed: %s", exc)
        return ({
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Database unavailable",
        }, status.HTTP_503_SERVICE_UNAVAILABLE)


def _build_health_payload() -> dict:
    """Build the standard health payload."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": getattr(settings, "ENVIRONMENT", "production"),
        "timestamp": datetime.now(UTC).isoformat(),
        "api_versioning": {
            "documented_prefix": "/chat and /pdf (OpenAPI)",
            "compatibility_prefix": "/api/v1",
            "mirrors_available": True,
        },
    }


def _register_health_routes(app: FastAPI) -> None:
    """Register health and ops endpoints."""

    @app.get(
        "/health",
        summary="Health check",
        description="Service liveness and build metadata.",
    )
    async def health_check():
        return _build_health_payload()

    @app.get(
        "/ops/health/database",
        summary="Database health check",
        description="Validates database connectivity (on-demand; may return 503 when degraded).",
    )
    async def database_health_check():
        payload, status_code = _build_database_health_payload()
        return JSONResponse(status_code=status_code, content=payload)

    @app.get(
        "/api/v1/health",
        summary="Versioned health check",
        description=f"Same payload as `GET /health`. Omitted from OpenAPI. {CANONICAL_API_NOTE}",
        include_in_schema=False,
    )
    async def health_check_v1():
        return _build_health_payload()

    @app.get(
        "/api/v1/ops/health/database",
        summary="Versioned database health check",
        description=f"Same behavior as `GET /ops/health/database`. Omitted from OpenAPI. {CANONICAL_API_NOTE}",
        include_in_schema=False,
    )
    async def database_health_check_v1():
        payload, status_code = _build_database_health_payload()
        return JSONResponse(status_code=status_code, content=payload)

    # Backward compatibility alias
    @app.get(
        "/health/database",
        summary="Legacy database health check",
        description=f"Legacy alias for `GET /ops/health/database`. Omitted from OpenAPI. {CANONICAL_API_NOTE}",
        include_in_schema=False,
    )
    async def database_health_check_legacy():
        payload, status_code = _build_database_health_payload()
        return JSONResponse(status_code=status_code, content=payload)


def _register_root_route(app: FastAPI) -> None:
    """Register a minimal JSON root for load balancers and quick sanity checks."""

    @app.get(
        "/",
        summary="API root",
        description="Minimal service root (JSON). Use `/docs` in non-production for OpenAPI.",
    )
    async def root():
        return {"message": "Backend is running"}


def _register_base_routes(app: FastAPI) -> None:
    """Register non-router application endpoints."""
    _register_health_routes(app)
    _register_root_route(app)


def _register_routers(app: FastAPI) -> None:
    from app.routes.chat import router as chat_router
    from app.routes.pdf_ingest import router as pdf_router

    app.include_router(chat_router, prefix="/chat", tags=["chat"])
    app.include_router(pdf_router, prefix="/pdf", tags=["pdf"])
    app.include_router(
        chat_router,
        prefix="/api/v1/chat",
        tags=["chat", "v1"],
        include_in_schema=False,
    )
    app.include_router(
        pdf_router,
        prefix="/api/v1/pdf",
        tags=["pdf", "v1"],
        include_in_schema=False,
    )


def create_app() -> FastAPI:
    docs_url = "/docs" if not _is_production() else None
    redoc_url = "/redoc" if not _is_production() else None
    openapi_url = "/openapi.json" if not _is_production() else None

    app = FastAPI(
        title="PDF Knowledge Chatbot",
        description="RAG-powered chatbot for PDF document content",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    _register_middleware(app)
    _register_exception_handlers(app)
    _register_base_routes(app)
    _register_routers(app)
    return app
