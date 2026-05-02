"""Machine list widget — backed by the FastAPI machines endpoints.

Polls `GET /api/machines` on a timer and exposes a `machineSelected`
signal so the main window can drive the Gantt + KPI panes from the same
data the PWA receives.

Architecture rule (CLAUDE.md §9): UI never talks to storage or registry
directly — only through `ui.api_client.ApiClient`.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
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

from ui.api_client import ApiClient, ApiError, MachineSummary
from utils.logger import log


class MachineManagerWidget(QWidget):
    """Live machine table — polls the API every `refresh_ms` ms."""

    machineSelected = pyqtSignal(str)  # emits machine_id when row selected

    COLUMNS = ("Machine", "Status", "Last cycle (ms)", "Cycles", "CV%")

    def __init__(
        self,
        api: ApiClient,
        parent: QWidget | None = None,
        refresh_ms: int = 2000,
    ) -> None:
        super().__init__(parent)
        self._api = api

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._status_label = QLabel("Loading machines…")
        toolbar.addWidget(self._status_label)
        toolbar.addStretch()
        refresh = QPushButton("Refresh now")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(self.COLUMNS), self)
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(self.COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(self._table.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(self._table.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        self._timer = QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    # ---- public API -----------------------------------------------------

    def refresh(self) -> None:
        try:
            machines = self._api.list_machines()
        except ApiError as exc:
            self._status_label.setText(f"API offline — {exc}")
            return

        self._status_label.setText(
            f"{len(machines)} machine(s)"
            if machines
            else "No machines configured (drop a YAML in config/machines/)."
        )

        previous = self._selected_id()
        self._table.setRowCount(len(machines))
        for row, m in enumerate(machines):
            self._populate_row(row, m)

        # Restore selection if the same machine still exists.
        if previous is not None:
            for row in range(self._table.rowCount()):
                if self._table.item(row, 0).data(0x0100) == previous:  # UserRole
                    self._table.selectRow(row)
                    break
        elif machines:
            self._table.selectRow(0)

    # ---- internals ------------------------------------------------------

    def _populate_row(self, row: int, m: MachineSummary) -> None:
        name = QTableWidgetItem(f"{m.name}  ·  {m.id}")
        name.setData(0x0100, m.id)  # Qt.UserRole
        self._table.setItem(row, 0, name)

        status = QTableWidgetItem(m.status)
        self._table.setItem(row, 1, status)

        last = QTableWidgetItem(
            "—" if m.last_cycle_ms is None else str(int(m.last_cycle_ms))
        )
        self._table.setItem(row, 2, last)

        count = QTableWidgetItem(str(m.cycle_count))
        self._table.setItem(row, 3, count)

        cv_text = "—" if m.max_cv_pct is None else f"{m.max_cv_pct:.1f}"
        cv_item = QTableWidgetItem(cv_text)
        self._table.setItem(row, 4, cv_item)

    def _selected_id(self) -> str | None:
        sel = self._table.selectedItems()
        if not sel:
            return None
        first = self._table.item(sel[0].row(), 0)
        if first is None:
            return None
        return first.data(0x0100)

    def _on_selection_changed(self) -> None:
        machine_id = self._selected_id()
        if machine_id is not None:
            log.debug("MachineManager selected", machine_id=machine_id)
            self.machineSelected.emit(machine_id)

    def closeEvent(self, event) -> None:  # noqa: D401, N802
        self._timer.stop()
        super().closeEvent(event)
