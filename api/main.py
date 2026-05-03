"""FastAPI app entrypoint for DS Machine Analyzer.

Run standalone:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Embedded: `main.py` builds an `AppState` and assigns it to
`app.state.app_state` before launching uvicorn programmatically.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import health, license, machines, packs, ws
from api.state import AppState, WSHub
from core.data_model import DataBusEvent
from core.machine_registry import MachineRegistry
from core.tier_profile import resolve_current_tier
from storage.sqlite_storage import SqliteStorage
from utils.logger import log

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEB_DIR = _PROJECT_ROOT / "web"
_DEFAULT_DB = _PROJECT_ROOT / "data" / "ds_machine_analyzer.db"
_DEFAULT_CONFIG_DIR = _PROJECT_ROOT / "config" / "machines"

_BROADCAST_EVENT_TYPES = {"cycle_summary", "cycle_anomaly", "alarm", "status_change"}


def _build_app_state_from_env() -> AppState:
    """When `uvicorn api.main:app` runs standalone, build registry from env."""
    config_dir = Path(os.getenv("DS_MA_CONFIG_DIR", str(_DEFAULT_CONFIG_DIR)))
    db_path = Path(os.getenv("DS_MA_DB_PATH", str(_DEFAULT_DB)))
    storage = SqliteStorage(db_path)
    tier = resolve_current_tier()
    registry = MachineRegistry(config_dir, storage=storage, tier=tier)
    return AppState(registry=registry, storage=storage)


def _make_ws_forwarder(machine_id: str, hub: WSHub):
    async def forwarder(event: DataBusEvent) -> None:
        if event.event_type not in _BROADCAST_EVENT_TYPES:
            return
        ts = (
            event.timestamp.isoformat()
            if isinstance(event.timestamp, datetime)
            else datetime.now(timezone.utc).isoformat()
        )
        await hub.broadcast(
            machine_id,
            {
                "type": event.event_type,
                "machine_id": event.machine_id,
                "timestamp": ts,
                "payload": event.payload,
            },
        )

    return forwarder


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize storage, load configs, register & start machines, mount
    WS forwarders. Reverse on shutdown.
    """
    state: AppState = getattr(app.state, "app_state", None) or _build_app_state_from_env()
    app.state.app_state = state

    log.info("API lifespan: starting")
    await state.storage.connect()

    configs = await state.registry.load_all_configs()
    if not configs:
        log.warning(
            "No machine_*.yaml found — API will run with empty registry",
            config_dir=str(state.registry.config_dir),
        )
    for cfg in configs:
        if not cfg.enabled:
            log.info("Skipping disabled machine", machine_id=cfg.machine_id)
            continue
        try:
            handle = await state.registry.register(cfg)
        except Exception as exc:  # noqa: BLE001
            # Tier violation, capacity overflow, etc. — log loudly and
            # skip the machine. Other machines keep loading.
            log.error(
                "Machine registration refused",
                machine_id=cfg.machine_id,
                error=str(exc),
            )
            continue
        await handle.bus.subscribe(
            f"ws_hub_{handle.machine_id}",
            _make_ws_forwarder(handle.machine_id, state.ws_hub),
        )

    await state.registry.start_all()

    # Retention cleanup — run once at startup, then every 6 hours.
    retention_task: asyncio.Task | None = None
    tier = state.registry.tier
    if tier is not None and tier.data_retention_days > 0:
        async def _retention_loop() -> None:
            while True:
                try:
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=tier.data_retention_days
                    )
                    await state.storage.delete_old_data(cutoff)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Retention cleanup failed", error=str(exc))
                await asyncio.sleep(6 * 3600)  # every 6 hours

        retention_task = asyncio.create_task(_retention_loop())
        log.info(
            "Retention cleanup enabled",
            days=tier.data_retention_days,
        )

    log.info("API lifespan: ready", machines=len(state.registry))

    try:
        yield
    finally:
        if retention_task is not None:
            retention_task.cancel()
        log.info("API lifespan: shutting down")
        await state.registry.stop_all()
        await state.storage.disconnect()
        log.info("API lifespan: shutdown complete")


app = FastAPI(
    title="DS Machine Analyzer API",
    description="API-first PLC analytics — Cycle / OEE / Event Log",
    version="0.1.0",
    lifespan=_lifespan,
)

# CORS: tighten via DS_MA_CORS_ORIGINS env var (comma-separated allowlist).
_cors_env = os.getenv("DS_MA_CORS_ORIGINS", "")
_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(license.router)
app.include_router(machines.router)
app.include_router(packs.router)
app.include_router(ws.router)

if (_WEB_DIR / "static").exists():
    app.mount("/web", StaticFiles(directory=_WEB_DIR / "static", html=True), name="web")
