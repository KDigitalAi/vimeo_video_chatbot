"""
Vercel serverless entry for the FastAPI application.

Vercel's Python build scans for a top-level binding named `app`, `application`,
or `handler`. A plain `from app.main import app` is often not detected; use an
explicit assignment after fixing sys.path.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import app as _fastapi_app

app = _fastapi_app
application = app
