"""
Vercel serverless function entry point for FastAPI app.

Vercel automatically detects the 'app' variable.
"""
import sys
import os

# Write to stderr for Vercel logs
def log(msg):
    try:
        sys.stderr.write(f"[API/INDEX] {msg}\n")
        sys.stderr.flush()
    except:
        pass

log("=" * 60)
log("Starting handler initialization")
log(f"Python version: {sys.version}")
log(f"Current dir: {os.getcwd()}")
log(f"__file__: {__file__}")

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
log(f"Parent dir: {parent_dir}")

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    log(f"Added {parent_dir} to sys.path")

log(f"Python path: {sys.path[:3]}...")  # Show first 3 entries

# Import and export FastAPI app
# Vercel looks for 'app' variable, not 'handler'
try:
    log("Attempting to import app.main...")
    from app.main import app
    
    log(f"✅ Successfully imported app. Type: {type(app).__name__}")
    
    # Verify app is a FastAPI instance
    if app is None:
        raise ImportError("FastAPI app is None - FastAPI import likely failed")
    
    if not hasattr(app, 'router'):
        raise ImportError("Imported 'app' is not a FastAPI instance")
    
    log(f"✅ App verified: has router={hasattr(app, 'router')}")
    
    # Export as 'app' - Vercel automatically detects this
    
except Exception as e:
    log(f"❌ Import failed: {type(e).__name__}: {str(e)}")
    import traceback
    log(traceback.format_exc())
    
    # If import fails, create minimal error handler
    try:
        log("Creating error handler app...")
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        app = FastAPI(title="Error Handler - Import Failed")
        
        @app.get("/{full_path:path}")
        @app.post("/{full_path:path}")
        @app.put("/{full_path:path}")
        @app.delete("/{full_path:path}")
        @app.patch("/{full_path:path}")
        async def error_handler(full_path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application failed to initialize",
                    "message": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "python_path": sys.path[:5],  # First 5 entries
                    "current_dir": os.getcwd(),
                    "parent_dir": parent_dir
                }
            )
        log("✅ Error handler app created")
        
    except Exception as fallback_error:
        log(f"❌ Error handler creation failed: {fallback_error}")
        import traceback as tb
        # Last resort: create a basic FastAPI app
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/{full_path:path}")
        async def error_route(full_path: str):
            return {
                "error": "Critical initialization failure",
                "primary_error": str(e),
                "fallback_error": str(fallback_error),
                "traceback": tb.format_exc()
            }
        log("✅ Basic error app created")

log(f"✅ Final app type: {type(app).__name__}")
log("=" * 60)
