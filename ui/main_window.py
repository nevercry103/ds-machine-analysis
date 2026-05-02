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
from utils.logger import log


class MainWindow(QMainWindow):
    """Desktop shell — left: machine list, right: Gantt of selected machine."""

    DEFAULT_BASE_URL = os.getenv("DS_MA_API_URL", "http://127.0.0.1:8000")

    def __init__(self, api: ApiClient | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DS Machine Analyzer Platform")
        self.setGeometry(100, 100, 1280, 800)

        self._api = api or ApiClient(self.DEFAULT_BASE_URL)

        self._machines = MachineManagerWidget(self._api, self)
        self._gantt = CycleGanttWidget(self._api, self)
        self._machines.machineSelected.connect(self._gantt.set_machine)

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
        status_bar.addPermanentWidget(self._api_status)
        self._refresh_api_status()

        log.info("MainWindow initialized", api_base=self._api._base_url)  # noqa: SLF001

    def _refresh_api_status(self) -> None:
        try:
            payload = self._api.health()
            self._api_status.setText(f"API: {payload.get('status', '?')}")
        except ApiError as exc:
            self._api_status.setText(f"API: offline ({exc})")

    def closeEvent(self, event) -> None:  # noqa: N802
        log.info("MainWindow closing")
        try:
            self._api.close()
        except Exception:
            pass
        event.accept()
