"""Replay Mode widget — time-travel debugging (F-005).

Lets the engineer pick a past cycle and scrub through it step by step,
viewing PLC tag values captured at each step boundary. Answers the
question: "why was Step 3 slow at 14:22 yesterday?"

Architecture rule: UI consumes the API only — no direct core imports.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.api_client import ApiClient, ApiError, CycleReplay, ReplayStep
from utils.logger import log


class ReplayWidget(QWidget):
    """Replay scrubber — cycle selector + step slider + tag value table."""

    def __init__(self, api: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._machine_id: str | None = None
        self._replay: CycleReplay | None = None
        self._cycle_ids: list[int] = []

        layout = QVBoxLayout(self)

        # ---- Toolbar: cycle selector ----
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Cycle:"))
        self._cycle_combo = QComboBox()
        self._cycle_combo.setMinimumWidth(200)
        self._cycle_combo.currentIndexChanged.connect(self._on_cycle_selected)
        toolbar.addWidget(self._cycle_combo)

        self._load_btn = QPushButton("Load replay")
        self._load_btn.clicked.connect(self._load_replay)
        toolbar.addWidget(self._load_btn)

        toolbar.addStretch()
        self._info_label = QLabel("Select a machine to browse past cycles.")
        toolbar.addWidget(self._info_label)
        layout.addLayout(toolbar)

        # ---- Step slider ----
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Step:"))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._on_step_changed)
        slider_row.addWidget(self._slider, stretch=1)
        self._step_label = QLabel("—")
        self._step_label.setMinimumWidth(200)
        slider_row.addWidget(self._step_label)
        layout.addLayout(slider_row)

        # ---- Tag values table ----
        self._tag_table = QTableWidget(0, 2, self)
        self._tag_table.setHorizontalHeaderLabels(["Tag", "Value"])
        header = self._tag_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tag_table.verticalHeader().setVisible(False)
        self._tag_table.setEditTriggers(self._tag_table.EditTrigger.NoEditTriggers)
        layout.addWidget(self._tag_table, stretch=1)

        # ---- Step timing bar ----
        self._timing_label = QLabel("")
        layout.addWidget(self._timing_label)

    def set_machine(self, machine_id: str) -> None:
        """Switch to a new machine — load recent cycle IDs for the combo."""
        self._machine_id = machine_id
        self._replay = None
        self._cycle_ids.clear()
        self._tag_table.setRowCount(0)
        self._slider.setMaximum(0)
        self._step_label.setText("—")
        self._timing_label.setText("")
        self._load_cycle_list()

    def _load_cycle_list(self) -> None:
        if self._machine_id is None:
            return
        try:
            cycles = self._api.get_recent_cycles(self._machine_id, limit=50)
        except ApiError as exc:
            self._info_label.setText(f"Error: {exc}")
            return

        self._cycle_combo.blockSignals(True)
        self._cycle_combo.clear()
        self._cycle_ids.clear()
        for c in cycles:
            self._cycle_ids.append(c.cycle_id)
            self._cycle_combo.addItem(
                f"#{c.cycle_id}  —  {c.total_ms} ms  ({len(c.steps)} steps)"
            )
        self._cycle_combo.blockSignals(False)

        if cycles:
            self._info_label.setText(f"{len(cycles)} cycle(s) available")
            self._cycle_combo.setCurrentIndex(0)
        else:
            self._info_label.setText("No cycles persisted yet.")

    def _on_cycle_selected(self, _index: int) -> None:
        """Auto-load replay when a cycle is picked from the combo."""
        self._load_replay()

    def _load_replay(self) -> None:
        idx = self._cycle_combo.currentIndex()
        if idx < 0 or idx >= len(self._cycle_ids) or self._machine_id is None:
            return

        cycle_id = self._cycle_ids[idx]
        try:
            self._replay = self._api.get_cycle_replay(self._machine_id, cycle_id)
        except ApiError as exc:
            self._info_label.setText(f"Replay error: {exc}")
            self._replay = None
            return

        r = self._replay
        n = len(r.steps)
        tag_info = f"  ·  {r.replay_tag_count} tag snapshots" if r.replay_tag_count else ""
        self._info_label.setText(
            f"Cycle #{r.cycle_id}  ·  {r.total_ms} ms  ·  {n} steps{tag_info}"
        )

        self._slider.blockSignals(True)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, n - 1))
        self._slider.setValue(0)
        self._slider.blockSignals(False)

        if n > 0:
            self._show_step(r.steps[0])
        else:
            self._tag_table.setRowCount(0)
            self._step_label.setText("—")

        log.debug(
            "Replay loaded",
            machine_id=self._machine_id,
            cycle_id=cycle_id,
            steps=n,
            tags=r.replay_tag_count,
        )

    def _on_step_changed(self, value: int) -> None:
        if self._replay is None or value >= len(self._replay.steps):
            return
        self._show_step(self._replay.steps[value])

    def _show_step(self, step: ReplayStep) -> None:
        # Step label
        self._step_label.setText(
            f"{step.index}. {step.name}  —  {step.duration_ms} ms"
        )

        # Timing
        started = step.started_at
        ended = step.ended_at
        if "T" in started:
            started = started.split("T")[1][:12]
        if "T" in ended:
            ended = ended.split("T")[1][:12]
        self._timing_label.setText(f"Start: {started}  →  End: {ended}")

        # Tag values
        tags = step.tag_values
        self._tag_table.setRowCount(len(tags))
        for row, (tag_name, tag_val) in enumerate(sorted(tags.items())):
            name_item = QTableWidgetItem(tag_name)
            val_item = QTableWidgetItem(str(tag_val))

            # Color bool values
            if isinstance(tag_val, bool):
                val_item.setForeground(
                    QColor("#22c55e") if tag_val else QColor("#ef4444")
                )

            self._tag_table.setItem(row, 0, name_item)
            self._tag_table.setItem(row, 1, val_item)

        if not tags:
            self._tag_table.setRowCount(1)
            empty = QTableWidgetItem("No replay tags configured for this machine")
            empty.setForeground(QColor("#9ca3af"))
            self._tag_table.setItem(0, 0, empty)
            self._tag_table.setItem(0, 1, QTableWidgetItem(""))
