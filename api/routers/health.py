"""Health check endpoints — liveness + readiness."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.state import AppState

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 if the API process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    """Readiness probe — 200 only when storage is connected and the
    machine registry has been initialized by the lifespan handler.

    Used by container orchestrators (Phase 4) and by the PWA's connection
    pill: a green light here means the WS is safe to subscribe.
    """
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="App state not initialized")

    storage_ok = getattr(state.storage, "_engine", None) is not None
    if not storage_ok:
        raise HTTPException(status_code=503, detail="Storage not connected")

    return {
        "status": "ready",
        "machines": len(state.registry),
        "ws_clients": sum(len(s) for s in state.ws_hub.clients.values()),
    }
