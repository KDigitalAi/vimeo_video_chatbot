# Function Invocation Failure Fixes

## Overview
This document outlines all fixes applied to resolve `FUNCTION_INVOCATION_FAILED` errors on Vercel serverless deployments.

## Issues Fixed

### 1. Settings Initialization Crashes
**Problem:** The `Settings()` class could raise `ValueError` during initialization if `ENVIRONMENT` was invalid, causing the entire application to crash.

**Fix:** Added multiple fallback layers in `app/config/settings.py`:
- Pre-validate `ENVIRONMENT` before creating `Settings()`
- Catch `ValueError` specifically and retry with safe defaults
- Last resort: Create a minimal `MinimalSettings` class if all else fails

**Location:** `app/config/settings.py` lines 97-147

### 2. Circular Import Dependencies
**Problem:** `app/database/supabase.py` imported `from app.services.vector_store_direct import get_supabase_direct` at module level, which could cause circular import issues or import-time failures.

**Fix:** Converted to lazy imports using helper functions:
- `_get_settings()` - lazy import of settings
- `_get_supabase_direct()` - lazy import of get_supabase_direct
- These are only called when `get_supabase()` is actually invoked

**Location:** `app/database/supabase.py` lines 3-12

### 3. Enhanced Error Handling in Entry Point
**Problem:** `api/index.py` had a single catch-all exception handler that didn't distinguish between import errors and other errors.

**Fix:** Separated error handling:
- Specific `ImportError` handler with detailed diagnostics
- General exception handler for other errors
- Both handlers create a minimal error app that can respond to requests
- Added Python version and path information to error responses

**Location:** `api/index.py` lines 1-94

### 4. Improved Diagnostic Endpoints
**Problem:** Limited visibility into what was failing during deployment.

**Fix:** Enhanced `/debug/routers` endpoint and added `/_logs` endpoint:
- `/debug/routers` now includes:
  - Router loading status
  - Environment variable status (without exposing values)
  - Python version
  - Import errors
  - Available routes
  - FastAPI availability status
- `/_logs` endpoint for Vercel-compatible log access

**Location:** `app/main.py` lines 308-406

## How to Check Application Logs

### Method 1: Vercel Dashboard
1. Go to your Vercel project dashboard
2. Click on the deployment
3. Click "Functions" tab
4. Click on the function (e.g., `api/index.py`)
5. View the "Logs" section

### Method 2: Diagnostic Endpoints
After deployment, visit these endpoints:

**Health Check:**
```
GET https://your-domain.vercel.app/health
```

**Router Status:**
```
GET https://your-domain.vercel.app/debug/routers
```
This shows:
- Which routers loaded successfully
- Which environment variables are set
- Available routes
- Any import errors

**Logs Endpoint:**
```
GET https://your-domain.vercel.app/_logs
```
Note: In Vercel, this endpoint provides diagnostic info. Full logs are in the Vercel dashboard.

### Method 3: Vercel CLI
```bash
vercel logs [deployment-url]
```

## Verification Checklist

After deployment, verify:

- [ ] `/health` endpoint returns `200 OK`
- [ ] `/debug/routers` shows all routers loaded
- [ ] `/debug/routers` shows environment variables are set
- [ ] No import errors in `/debug/routers` response
- [ ] Main endpoints (e.g., `/chat/query`) are accessible
- [ ] Check Vercel deployment logs for any warnings

## Common Issues and Solutions

### Issue: "ImportError: cannot import name 'X'"
**Solution:** Check `/debug/routers` to see which module failed. Usually indicates:
- Missing `__init__.py` file
- Circular import (now fixed with lazy imports)
- Missing dependency in `requirements.txt`

### Issue: "Settings validation error"
**Solution:** Ensure `ENVIRONMENT` is set to one of: `development`, `staging`, `production`
- Check Vercel environment variables
- Default is now `production` if invalid

### Issue: "SUPABASE_URL is not properly configured"
**Solution:** Set environment variables in Vercel:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `OPENAI_API_KEY`
- `VIMEO_ACCESS_TOKEN` (if needed)

### Issue: Router not loading
**Solution:** Check `/debug/routers` to see which router failed:
- Look at `router_status` in the response
- Check Vercel logs for the specific import error
- The app will still start even if some routers fail

## Code Structure

### Entry Point: `api/index.py`
- Safe import with multiple error handlers
- Always exports a `handler` (either main app or error app)
- Provides detailed error messages

### Main App: `app/main.py`
- All imports wrapped in try/except
- Routers load independently
- App can start even if some routers fail
- Comprehensive exception handlers

### Settings: `app/config/settings.py`
- Multiple fallback layers
- Never crashes on initialization
- Creates minimal settings if full initialization fails

### Database: `app/database/supabase.py`
- Lazy imports prevent circular dependencies
- Detailed error logging
- Graceful failure if Supabase not configured

## Testing Locally

Before deploying, test locally:

```bash
# Test that app imports successfully
python -c "from app.main import app; print('OK')"

# Test that api/index.py works
python -c "from api.index import handler; print('OK')"

# Run the app
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Test endpoints
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/debug/routers
```

## Deployment

1. Ensure all environment variables are set in Vercel
2. Deploy: `vercel --prod` or push to main branch
3. Check deployment logs immediately
4. Test `/health` and `/debug/routers` endpoints
5. If errors persist, check `/debug/routers` for specific issues

## Summary

All fixes ensure:
- ✅ No unhandled exceptions during import
- ✅ No circular import issues
- ✅ Graceful degradation if components fail
- ✅ Detailed diagnostics for troubleshooting
- ✅ Application always responds (even if degraded)
- ✅ Comprehensive error logging

The application should now deploy successfully on Vercel even if some optional components fail to load.

