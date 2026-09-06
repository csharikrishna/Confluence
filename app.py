"""
Confluence Environmental Intelligence API - Root Gateway & Process Entrypoint

This module acts as the root gateway and transparent alias for `backend.app`.
It preserves 100% backward compatibility with:
- Procfile (`web: uvicorn app:app --host 0.0.0.0 --port $PORT`)
- Render deployment configurations (`render.yaml`)
- Docker containers & dev scripts
- Existing test suites and mocks (@patch("app.get_environmental_snapshot"), etc.)
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_REPO_ROOT, "backend")

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app as _backend_app

# Alias this module to backend.app in sys.modules so imports and mock.patch("app.X")
# directly resolve and modify backend.app's namespace
sys.modules[__name__] = _backend_app
