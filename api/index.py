# Safe import with error handling to prevent serverless function crashes
try:
    from app.main import app
    # Explicit export for Vercel serverless
    handler = app
except Exception as e:
    # If app fails to import, create a minimal error handler
    import logging
    import json
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import app.main: {e}")
    import traceback
    logger.error(traceback.format_exc())
    
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
                "path": path
            }
        )
    
    handler = error_app
    app = error_app

