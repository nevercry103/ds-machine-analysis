"""API endpoint tests using FastAPI's in-process test client."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app as fastapi_app
from api.state import AppState
from core.machine_registry import MachineRegistry
from storage.sqlite_storage import SqliteStorage


@pytest.fixture
async def client(tmp_path: Path):
    """Build a fresh AppState rooted at tmp_path so tests don't share state.

    No machine YAMLs are present, so the registry stays empty — the API
    should still answer /api/health and /api/machines (empty list).
    """
    storage = SqliteStorage(tmp_path / "test.db")
    registry = MachineRegistry(tmp_path, storage=storage)
    fastapi_app.state.app_state = AppState(registry=registry, storage=storage)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # FastAPI lifespan runs on startup via the ASGI lifespan protocol;
        # AsyncClient doesn't trigger it, so do it manually.
        await storage.connect()
        try:
            yield ac
        finally:
            await storage.disconnect()


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready(client: AsyncClient):
    resp = await client.get("/api/ready")
    assert resp.status_code == 200
    body = resp.json()
    # /api/ready now reports live state — exercise it.
    assert body["status"] == "ready"
    assert body["machines"] == 0
    assert body["ws_clients"] == 0


@pytest.mark.asyncio
async def test_ready_503_when_state_missing(tmp_path):
    """If lifespan never ran, readiness must hard-fail with 503 so a
    container orchestrator sees the pod as unready."""
    # Strip any state from previous tests in the same module.
    fastapi_app.state.app_state = None
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/ready")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_machines_empty(client: AsyncClient):
    resp = await client.get("/api/machines")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_machine_not_found(client: AsyncClient):
    resp = await client.get("/api/machines/does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cycles_invalid_limit(client: AsyncClient):
    resp = await client.get("/api/machines/m1/cycles?limit=0")
    assert resp.status_code == 400
