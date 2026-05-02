"""API routers — one module per resource group.

Convention: each router module exports a `router = APIRouter(prefix=...)`.
Mount in `api/main.py`. Keep route handlers thin — they translate
HTTP/WebSocket to/from core layer calls, nothing more.
"""
