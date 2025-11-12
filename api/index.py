# Safe import with error handling to prevent serverless function crashes
# This is the Vercel serverless function entry point
import sys
import os

# Ensure we're in the right environment
try:
    # Try to import the main app
    from app.main import app
    
    # Check if app is None (FastAPI import failed)
    if app is None:
        raise ImportError("FastAPI app is None - FastAPI import likely failed")
    
    # Explicit export for Vercel serverless
    handler = app
    
except ImportError as ie:
    # Handle import errors specifically
    import logging
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"ImportError importing app.main: {ie}")
    import traceback
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    
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
                "python_path": sys.path[:5],  # First 5 entries
                "diagnostic": "Check Vercel deployment logs for full traceback"
            }
        )
    
    handler = error_app
    app = error_app
    
except Exception as e:
    # If app fails to import for any other reason, create a minimal error handler
    import logging
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import app.main: {type(e).__name__}: {e}")
    import traceback
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    
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
                "python_version": sys.version
            }
        )
    
    handler = error_app
    app = error_app

