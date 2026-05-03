"""Event Log widget — Pillar 3.

Displays recent alarms, anomalies, downtime tags, and status changes
for the selected machine. Polls /api/machines/{id}/events periodically
and refreshes on WS alarm/anomaly events.

Architecture rule: UI consumes the API only — no direct core imports.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.api_client import ApiClient, ApiError, EventEntry
from ui.theme import SEVERITY_COLORS, format_iso_time
from utils.logger import log


class EventLogWidget(QWidget):
    """Event log table — polls the events endpoint for the selected machine."""

    COLUMNS = ("Time", "Severity", "Category", "Message", "Ack")

    def __init__(
        self,
        api: ApiClient,
        parent: QWidget | None = None,
        refresh_ms: int = 10000,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._machine_id: str | None = None

        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self._caption = QLabel("Select a machine to view events.")
        toolbar.addWidget(self._caption)
        toolbar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        # Table
        self._table = QTableWidget(0, len(self.COLUMNS), self)
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(self._table.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(self._table.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        # Timer
        self._timer = QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self.refresh)

    def set_machine(self, machine_id: str) -> None:
        self._machine_id = machine_id
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        if self._machine_id is None:
            return
        try:
            events = self._api.get_events(self._machine_id, limit=100)
        except ApiError as exc:
            self._caption.setText(f"Events error — {exc}")
            return

        self._caption.setText(
            f"{self._machine_id} — {len(events)} event(s)"
            if events
            else f"{self._machine_id} — no events"
        )

        self._table.setRowCount(len(events))
        for row, ev in enumerate(events):
            self._populate_row(row, ev)

    def _populate_row(self, row: int, ev: EventEntry) -> None:
        # Time — show just time portion if today, else full
        ts = format_iso_time(ev.timestamp)
        self._table.setItem(row, 0, QTableWidgetItem(ts))

        # Severity with color
        sev_item = QTableWidgetItem(ev.severity)
        color = SEVERITY_COLORS.get(ev.severity)
        if color:
            sev_item.setForeground(color)
        self._table.setItem(row, 1, sev_item)

        # Category
        self._table.setItem(row, 2, QTableWidgetItem(ev.category))

        # Message
        msg = ev.message or ev.code or "—"
        self._table.setItem(row, 3, QTableWidgetItem(msg))

        # Ack status
        ack_text = "yes" if ev.acknowledged else "—"
        self._table.setItem(row, 4, QTableWidgetItem(ack_text))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(event)
