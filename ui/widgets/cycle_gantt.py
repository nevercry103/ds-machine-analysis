"""Gantt widget — renders the most-recent cycle from the API.

Pulls `GET /api/machines/{id}/cycles?limit=1` whenever a different
machine is selected upstream. Drawing is pure `QPainter` so we do not
add a matplotlib dependency to the desktop bundle (Phase 5 PyInstaller
size matters).

The bottleneck step is highlighted in fault-red. Hover/zoom is Phase 3
polish — we ship the static render now to satisfy the Phase 1 exit
criterion: "Gantt widget renders cycle from API response".
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.api_client import ApiClient, ApiError, CycleSummary
from utils.logger import log


class _GanttCanvas(QWidget):
    """Pure paint widget — owns no data fetching, just renders a cycle."""

    BAR_HEIGHT = 28
    BAR_GAP = 8
    LEFT_PAD = 140  # room for step name
    RIGHT_PAD = 80  # room for "1234 ms" label

    NORMAL_COLOR = QColor("#3b82f6")  # blue-500
    BOTTLENECK_COLOR = QColor("#ef4444")  # red-500
    GRID_COLOR = QColor("#e5e7eb")
    TEXT_COLOR = QColor("#1f2937")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cycle: CycleSummary | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)

    def set_cycle(self, cycle: CycleSummary | None) -> None:
        self._cycle = cycle
        # Resize to fit the step count comfortably.
        if cycle is not None and cycle.steps:
            needed = (
                len(cycle.steps) * (self.BAR_HEIGHT + self.BAR_GAP) + 60
            )
            self.setMinimumHeight(max(220, needed))
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), self.palette().window())

            if self._cycle is None or not self._cycle.steps:
                self._draw_empty(painter)
                return

            self._draw_cycle(painter, self._cycle)
        finally:
            painter.end()

    # ---- drawing helpers ------------------------------------------------

    def _draw_empty(self, painter: QPainter) -> None:
        painter.setPen(self.TEXT_COLOR)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No cycle data yet — start a machine and wait for the first cycle.",
        )

    def _draw_cycle(self, painter: QPainter, cycle: CycleSummary) -> None:
        total = max(1, cycle.total_ms)
        plot_left = self.LEFT_PAD
        plot_right = self.width() - self.RIGHT_PAD
        plot_width = max(50, plot_right - plot_left)

        # Header
        font = painter.font()
        bold = QFont(font)
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(self.TEXT_COLOR)
        painter.drawText(
            10,
            22,
            f"{cycle.machine_id} — cycle #{cycle.cycle_id}  ·  total {total} ms",
        )
        painter.setFont(font)

        # Each step bar
        cursor_ms = 0
        y = 40
        for step in cycle.steps:
            x = plot_left + int(plot_width * (cursor_ms / total))
            w = max(2, int(plot_width * (step.duration_ms / total)))

            is_bottleneck = (
                cycle.bottleneck_step_index is not None
                and step.index == cycle.bottleneck_step_index
            )
            color = self.BOTTLENECK_COLOR if is_bottleneck else self.NORMAL_COLOR

            # Step name
            painter.setPen(self.TEXT_COLOR)
            painter.drawText(
                QRect(0, y, self.LEFT_PAD - 8, self.BAR_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{step.index}. {step.name}",
            )

            # Bar
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color))
            painter.drawRoundedRect(x, y, w, self.BAR_HEIGHT, 4, 4)

            # ms label on the right
            painter.setPen(self.TEXT_COLOR)
            painter.drawText(
                QRect(plot_right + 4, y, self.RIGHT_PAD - 8, self.BAR_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{step.duration_ms} ms",
            )

            cursor_ms += step.duration_ms
            y += self.BAR_HEIGHT + self.BAR_GAP

        # Plot border
        painter.setPen(QPen(self.GRID_COLOR))
        painter.drawLine(plot_left, 36, plot_left, y)
        painter.drawLine(plot_right, 36, plot_right, y)


class CycleGanttWidget(QWidget):
    """Gantt + status caption — fetches the latest cycle on `set_machine()`."""

    def __init__(self, api: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._machine_id: str | None = None

        layout = QVBoxLayout(self)
        self._caption = QLabel("Select a machine to view its latest cycle.")
        layout.addWidget(self._caption)

        self._canvas = _GanttCanvas(self)
        layout.addWidget(self._canvas, stretch=1)

    def set_machine(self, machine_id: str) -> None:
        """Switch to `machine_id` and pull its most recent cycle."""
        self._machine_id = machine_id
        self.refresh()

    def refresh(self) -> None:
        if self._machine_id is None:
            return
        try:
            cycles = self._api.get_recent_cycles(self._machine_id, limit=1)
        except ApiError as exc:
            self._caption.setText(f"API offline — {exc}")
            self._canvas.set_cycle(None)
            return

        if not cycles:
            self._caption.setText(
                f"{self._machine_id}: no cycles persisted yet."
            )
            self._canvas.set_cycle(None)
            return

        cycle = cycles[0]
        cv_part = ""
        if hasattr(cycle, "max_cv_pct") and cycle.max_cv_pct is not None:
            cv_part = f"  ·  CV {cycle.max_cv_pct:.1f}%"
        self._caption.setText(
            f"{self._machine_id} — cycle #{cycle.cycle_id}  ·  "
            f"{len(cycle.steps)} steps  ·  {cycle.total_ms} ms{cv_part}"
        )
        self._canvas.set_cycle(cycle)
        log.debug(
            "CycleGantt rendered",
            machine_id=self._machine_id,
            cycle_id=cycle.cycle_id,
            steps=len(cycle.steps),
        )

    def update_cycle(self, cycle_data: dict) -> None:
        """Backwards-compatible entrypoint kept for the WS push hook
        (Phase 2 will wire WebSocket to the desktop). Accepts the
        `cycle_summary` payload shape published by `CycleProcessor`.
        """
        if not cycle_data or "steps" not in cycle_data:
            return
        from ui.api_client import CycleSummary, StepSummary  # local import — no cycle

        cycle = CycleSummary(
            machine_id=self._machine_id or "",
            cycle_id=int(cycle_data.get("cycle_id", 0)),
            total_ms=int(cycle_data.get("total_ms", 0)),
            steps=[
                StepSummary(
                    index=int(s.get("index", i + 1)),
                    name=s.get("name", f"Step {i + 1}"),
                    duration_ms=int(s.get("duration_ms", 0)),
                )
                for i, s in enumerate(cycle_data["steps"])
            ],
            bottleneck_step_index=cycle_data.get("bottleneck_step_index"),
        )
        self._canvas.set_cycle(cycle)
