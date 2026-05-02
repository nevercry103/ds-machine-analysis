"""API tests for Pillar 2 (OEE) and Pillar 3 (events + downtime) endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app as fastapi_app
from api.state import AppState
from core.config_model import MachineConfigSchema
from core.machine_registry import MachineRegistry
from core.tier_profile import load_tier
from storage.sqlite_storage import SqliteStorage


@pytest.fixture
async def full_pillars_client(tmp_path: Path):
    """Boot the API with one full-pillars machine on tier_unlimited."""
    machines_dir = tmp_path / "machines"
    machines_dir.mkdir()
    # Copy the shipped sample (it declares tier_5 + all pillars enabled).
    sample = Path("config/machines/machine_full_pillars.yaml.sample").read_text(
        encoding="utf-8"
    )
    (machines_dir / "machine_full_pillars.yaml").write_text(sample, encoding="utf-8")

    storage = SqliteStorage(tmp_path / "test.db")
    await storage.connect()
    tier = load_tier("tier_unlimited")
    registry = MachineRegistry(machines_dir, storage=storage, tier=tier)

    # Manually load + register, then start the *processors* (cycle/oee/events)
    # so the bus has subscribers — but DO NOT start the adapter, otherwise
    # the simulator thread would run and pollute the test.
    configs = await registry.load_all_configs()
    for cfg in configs:
        handle = await registry.register(cfg)
        await handle.processor.start()
        if handle.oee is not None:
            await handle.oee.start()
        if handle.events is not None:
            await handle.events.start()

    fastapi_app.state.app_state = AppState(registry=registry, storage=storage)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            for h in registry.all():
                if h.events is not None:
                    await h.events.stop()
                if h.oee is not None:
                    await h.oee.stop()
                await h.processor.stop()
                await h.bus.shutdown()
            await storage.disconnect()


@pytest.mark.asyncio
async def test_oee_endpoint_returns_zero_at_start(full_pillars_client: AsyncClient):
    """No cycles run yet — OEE returns a zero snapshot (not 404)."""
    resp = await full_pillars_client.get("/api/machines/machine_full_pillars/oee")
    assert resp.status_code == 200
    body = resp.json()
    assert body["machine_id"] == "machine_full_pillars"
    assert body["window_minutes"] == 60
    assert body["cycles_completed"] == 0
    assert body["oee"] == 0.0


@pytest.mark.asyncio
async def test_downtime_reasons_listed(full_pillars_client: AsyncClient):
    resp = await full_pillars_client.get(
        "/api/machines/machine_full_pillars/downtime/reasons"
    )
    assert resp.status_code == 200
    reasons = resp.json()
    assert "material_out" in reasons
    assert "setup_changeover" in reasons


@pytest.mark.asyncio
async def test_downtime_post_persists_and_returns(full_pillars_client: AsyncClient):
    # Pillar 3 logger needs to be running so downtime gets persisted.
    state = fastapi_app.state.app_state
    handle = state.registry.get("machine_full_pillars")
    assert handle.events is not None
    # Start the logger ourselves (we skipped registry.start_all in fixture).

    resp = await full_pillars_client.post(
        "/api/machines/machine_full_pillars/downtime",
        json={"reason": "material_out", "note": "out of caps", "by": "ha"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["category"] == "downtime"
    assert body["code"] == "DOWNTIME_MATERIAL_OUT"
    assert "ha" in body["message"]
    assert body["acknowledged"] is False


@pytest.mark.asyncio
async def test_downtime_post_rejects_unknown_reason(
    full_pillars_client: AsyncClient,
):
    resp = await full_pillars_client.post(
        "/api/machines/machine_full_pillars/downtime",
        json={"reason": "frobnitz", "by": "ha"},
    )
    assert resp.status_code == 400
    assert "Unknown downtime reason" in resp.text


@pytest.mark.asyncio
async def test_events_listing_empty_at_start(full_pillars_client: AsyncClient):
    resp = await full_pillars_client.get(
        "/api/machines/machine_full_pillars/events"
    )
    assert resp.status_code == 200
    assert resp.json() == []
