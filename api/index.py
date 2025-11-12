# Safe import with error handling to prevent serverless function crashes
# This is the Vercel serverless function entry point
import sys
import os
from pathlib import Path

# CRITICAL: Add project root to sys.path for Vercel serverless
# Vercel runs from /var/task, so we need to add the project root
project_root = Path(__file__).parent.parent
project_root_str = str(project_root)

# Add project root to sys.path if not already there
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Ensure we're in the right environment
try:
    # Try to import the main app
    from app.main import app
    
    # Check if app is None (FastAPI import failed)
    if app is None:
        raise ImportError("FastAPI app is None - FastAPI import likely failed")
    
    # Verify app is a FastAPI instance
    if not hasattr(app, 'router'):
        raise ImportError("Imported 'app' is not a FastAPI instance")
    
    # Explicit export for Vercel serverless
    # Vercel Python automatically detects FastAPI apps, but we export both for compatibility
    handler = app
    
    # Log successful import (only in development)
    if os.getenv("VERCEL_ENV") != "production":
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.info("✅ Successfully imported FastAPI app from app.main")
        logger.info(f"Python path (first 5): {sys.path[:5]}")
        logger.info(f"Project root: {project_root_str}")
    
except ImportError as ie:
    # Handle import errors specifically
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"ImportError importing app.main: {ie}")
    import traceback
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    logger.error(f"Python path: {sys.path[:10]}")
    logger.error(f"Project root: {project_root}")
    logger.error(f"Current working directory: {os.getcwd()}")
    
    # Try to import FastAPI for error handler
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        
        # Create minimal error app
        error_app = FastAPI(title="Error Handler - Import Failed")
        
        @error_app.get("/{path:path}")
        @error_app.post("/{path:path}")
        async def error_endpoint(request: Request, path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed - Import Error",
                    "message": str(ie),
                    "path": path,
                    "python_version": sys.version,
                    "python_path": sys.path[:10],
                    "project_root": str(project_root),
                    "cwd": os.getcwd(),
                    "diagnostic": "Check Vercel deployment logs for full traceback"
                }
            )
        
        handler = error_app
        app = error_app
    except ImportError:
        # If FastAPI itself can't be imported, create a minimal WSGI-like handler
        def handler(environ, start_response):
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'application/json')]
            body = f'{{"error": "Import failed", "message": "{str(ie)}", "python_path": {sys.path[:5]}}}'
            start_response(status, headers)
            return [body.encode()]
        
        app = None
    
except Exception as e:
    # If app fails to import for any other reason, create a minimal error handler
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import app.main: {type(e).__name__}: {e}")
    import traceback
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    logger.error(f"Python path: {sys.path[:10]}")
    logger.error(f"Project root: {project_root}")
    logger.error(f"Current working directory: {os.getcwd()}")
    
    # Try to import FastAPI for error handler
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        
        # Create minimal error app
        error_app = FastAPI(title="Error Handler")
        
        @error_app.exception_handler(Exception)
        async def error_handler(request: Request, exc: Exception):
            logger.error(f"Application error: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "message": str(exc),
                    "error_type": type(exc).__name__,
                    "detail": "Please check server logs for more information"
                }
            )
        
        @error_app.get("/{path:path}")
        @error_app.post("/{path:path}")
        async def error_endpoint(request: Request, path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "message": "The application failed to start. Please check server logs.",
                    "path": path,
                    "python_version": sys.version,
                    "python_path": sys.path[:10],
                    "project_root": str(project_root),
                    "cwd": os.getcwd()
                }
            )
        
        handler = error_app
        app = error_app
    except ImportError:
        # If FastAPI itself can't be imported, create a minimal WSGI-like handler
        def handler(environ, start_response):
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'application/json')]
            body = f'{{"error": "Initialization failed", "message": "{str(e)}", "error_type": "{type(e).__name__}"}}'
            start_response(status, headers)
            return [body.encode()]
        
        app = None

# Ensure handler is always defined (fallback for edge cases)
if 'handler' not in globals() or handler is None:
    # Ultimate fallback - create a minimal ASGI handler
    async def handler(scope, receive, send):
        if scope["type"] == "http":
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "Handler not properly initialized"}',
            })
