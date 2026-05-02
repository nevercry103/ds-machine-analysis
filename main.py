"""DS Machine Analyzer — entry point.

Two run modes (controlled by `--headless` flag or `DS_MA_HEADLESS=1` env):

1. **Headless** — pure asyncio: starts the FastAPI/uvicorn server, the
   Machine Registry, and the protocol adapters. No GUI. Suitable for
   server (Mode 1/2) and Raspberry Pi gateway deployments.

2. **Desktop** — same as headless plus a PyQt6 main window. The GUI is
   one of several API consumers; uvicorn runs in a worker thread so the
   Qt event loop stays in the main thread.

CLI:
    python main.py                 # GUI + API
    python main.py --headless      # API only
    python main.py --port 9000     # custom API port
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import threading
from pathlib import Path

import uvicorn

from api.main import app as fastapi_app
from api.state import AppState
from core.machine_registry import MachineRegistry
from core.tier_profile import resolve_current_tier
from storage.sqlite_storage import SqliteStorage
from utils.logger import log

_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_DB = _PROJECT_ROOT / "data" / "ds_machine_analyzer.db"
_DEFAULT_CONFIG_DIR = _PROJECT_ROOT / "config" / "machines"


def _ensure_dirs() -> None:
    (_PROJECT_ROOT / "config" / "machines").mkdir(parents=True, exist_ok=True)
    (_PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    (_PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)


def _build_state(config_dir: Path, db_path: Path) -> AppState:
    storage = SqliteStorage(db_path)
    tier = resolve_current_tier()
    registry = MachineRegistry(config_dir, storage=storage, tier=tier)
    return AppState(registry=registry, storage=storage)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ds-machine-analyzer")
    parser.add_argument(
        "--headless",
        action="store_true",
        default=os.getenv("DS_MA_HEADLESS", "0") == "1",
        help="Run API only, no PyQt6 GUI.",
    )
    parser.add_argument("--host", default=os.getenv("DS_MA_API_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("DS_MA_API_PORT", "8000"))
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(os.getenv("DS_MA_CONFIG_DIR", str(_DEFAULT_CONFIG_DIR))),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(os.getenv("DS_MA_DB_PATH", str(_DEFAULT_DB))),
    )
    return parser.parse_args()


def _run_uvicorn(host: str, port: int) -> uvicorn.Server:
    """Build and return a uvicorn.Server bound to the FastAPI app.

    The caller decides whether to `server.run()` (blocking) or
    `Thread(target=server.run).start()` (non-blocking, alongside Qt).
    """
    config = uvicorn.Config(
        app=fastapi_app,
        host=host,
        port=port,
        log_level="info",
        # `loop="asyncio"` keeps things simple on Windows.
        loop="asyncio",
    )
    return uvicorn.Server(config)


def _run_headless(args: argparse.Namespace) -> int:
    state = _build_state(args.config_dir, args.db_path)
    fastapi_app.state.app_state = state
    server = _run_uvicorn(args.host, args.port)
    log.info(
        "DS Machine Analyzer (headless)",
        host=args.host,
        port=args.port,
        config_dir=str(args.config_dir),
    )
    try:
        server.run()
    except KeyboardInterrupt:
        log.info("Interrupted")
    return 0


def _run_desktop(args: argparse.Namespace) -> int:
    # PyQt6 is optional — if it's not importable (or the bundled UI is
    # not yet refactored), fall back to headless with a clear message.
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore
        from ui.main_window import MainWindow  # type: ignore
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "PyQt6 GUI not available; running headless",
            error=str(exc),
        )
        return _run_headless(args)

    state = _build_state(args.config_dir, args.db_path)
    fastapi_app.state.app_state = state

    server = _run_uvicorn(args.host, args.port)

    api_thread = threading.Thread(
        target=server.run,
        name="ds-ma-api",
        daemon=True,
    )
    api_thread.start()
    log.info(
        "DS Machine Analyzer (desktop)",
        host=args.host,
        port=args.port,
        config_dir=str(args.config_dir),
    )

    qt_app = QApplication([])
    # Desktop talks to its own embedded API over loopback. Honour the
    # runtime port so `--port 9000` works end-to-end.
    api_base = f"http://127.0.0.1:{args.port}"
    from ui.api_client import ApiClient  # local import — Qt-side only

    window = MainWindow(api=ApiClient(api_base))
    window.show()
    try:
        return qt_app.exec()
    finally:
        # Ask uvicorn to exit cleanly when the GUI closes.
        server.should_exit = True
        with contextlib.suppress(Exception):
            api_thread.join(timeout=5.0)


def main() -> int:
    _ensure_dirs()
    args = _parse_args()
    if args.headless:
        return _run_headless(args)
    return _run_desktop(args)


if __name__ == "__main__":
    sys.exit(main())
