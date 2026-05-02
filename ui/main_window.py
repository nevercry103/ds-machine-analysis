"""Main PyQt6 window — desktop view for the Machine Analyzer.

This window is one of several API consumers (alongside the PWA, CLI, and
3rd-party MES). It NEVER imports `core/`, `storage/`, or `plc/`
directly — every fetch goes through `ui.api_client.ApiClient`, which
talks to the same FastAPI server the PWA does.

Architecture rule (CLAUDE.md §4): "API is the spine. PyQt6, PWA, CLI all
consume the same FastAPI endpoints."
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QWidget,
)

from ui.api_client import ApiClient, ApiError
from ui.widgets import CycleGanttWidget, MachineManagerWidget
from ui.ws_client import MachineWSClient
from utils.logger import log


class MainWindow(QMainWindow):
    """Desktop shell — left: machine list, right: Gantt of selected machine.

    The selected machine receives live updates via WebSocket; the machine
    list continues to poll (no WS endpoint for the full list).
    """

    DEFAULT_BASE_URL = os.getenv("DS_MA_API_URL", "http://127.0.0.1:8000")

    def __init__(self, api: ApiClient | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DS Machine Analyzer Platform")
        self.setGeometry(100, 100, 1280, 800)

        self._api = api or ApiClient(self.DEFAULT_BASE_URL)
        self._ws: MachineWSClient | None = None

        self._machines = MachineManagerWidget(self._api, self)
        self._gantt = CycleGanttWidget(self._api, self)
        self._machines.machineSelected.connect(self._on_machine_selected)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._machines)
        splitter.addWidget(self._gantt)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        self._api_status = QLabel("API: checking…")
        self._ws_status = QLabel("")
        status_bar.addPermanentWidget(self._ws_status)
        status_bar.addPermanentWidget(self._api_status)
        self._refresh_api_status()

        log.info("MainWindow initialized", api_base=self._api._base_url)  # noqa: SLF001

    # ---- machine selection + WS lifecycle --------------------------------

    def _on_machine_selected(self, machine_id: str) -> None:
        """Switch Gantt to the selected machine and start a WS subscription."""
        self._gantt.set_machine(machine_id)
        self._start_ws(machine_id)

    def _start_ws(self, machine_id: str) -> None:
        """(Re)connect WS for the newly selected machine."""
        self._stop_ws()
        self._ws = MachineWSClient(
            self._api._base_url,  # noqa: SLF001
            machine_id,
            parent=self,
        )
        self._ws.eventReceived.connect(self._on_ws_event)
        self._ws.connected.connect(
            lambda: self._ws_status.setText(f"WS: {machine_id}")
        )
        self._ws.disconnected.connect(
            lambda: self._ws_status.setText("WS: reconnecting…")
        )
        self._ws.start()

    def _stop_ws(self) -> None:
        if self._ws is not None:
            self._ws.stop()
            self._ws = None
            self._ws_status.setText("")

    def _on_ws_event(self, msg: dict) -> None:
        """Dispatch incoming WS events to the right widget."""
        event_type = msg.get("type", "")
        payload = msg.get("payload", {})

        if event_type == "cycle_summary":
            self._gantt.update_cycle(payload)
            self._machines.refresh()

        elif event_type == "cycle_anomaly":
            step = payload.get("step_name", "?")
            cv = payload.get("cv_pct", 0)
            self.statusBar().showMessage(
                f"Variance anomaly: step '{step}' CV={cv:.1f}%", 10000
            )

    # ---- helpers ---------------------------------------------------------

    def _refresh_api_status(self) -> None:
        try:
            payload = self._api.health()
            self._api_status.setText(f"API: {payload.get('status', '?')}")
        except ApiError as exc:
            self._api_status.setText(f"API: offline ({exc})")

    def closeEvent(self, event) -> None:  # noqa: N802
        log.info("MainWindow closing")
        self._stop_ws()
        try:
            self._api.close()
        except Exception:
            pass
        event.accept()
