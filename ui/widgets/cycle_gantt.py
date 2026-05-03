"""Gantt widget — renders cycle steps as horizontal bars.

Pulls `GET /api/machines/{id}/cycles?limit=1` whenever a different
machine is selected upstream. Drawing is pure `QPainter` so we do not
add a matplotlib dependency to the desktop bundle (Phase 5 PyInstaller
size matters).

Features:
- Bottleneck step highlighted in red
- Hover: hovered bar brightens, tooltip shows step detail
- Zoom: mouse wheel scales the time axis; Ctrl+0 resets
- Scroll: horizontal scroll when zoomed in
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ui.api_client import ApiClient, ApiError, CycleSummary
from ui.theme import BLUE_400, BLUE_500, GRAY_200, GRAY_800, RED_400, RED_500
from utils.logger import log


@dataclass
class _BarHit:
    """Cached geometry for one step bar — used for hover hit-testing."""

    step_index: int
    step_name: str
    duration_ms: int
    pct: float
    is_bottleneck: bool
    rect: QRect


class _GanttCanvas(QWidget):
    """Pure paint widget with hover highlight and zoom."""

    BAR_HEIGHT = 28
    BAR_GAP = 8
    LEFT_PAD = 140
    RIGHT_PAD = 80
    HEADER_HEIGHT = 40

    NORMAL_COLOR = BLUE_500
    HOVER_COLOR = BLUE_400
    BOTTLENECK_COLOR = RED_500
    BOTTLENECK_HOVER = RED_400
    GRID_COLOR = GRAY_200
    TEXT_COLOR = GRAY_800

    ZOOM_MIN = 1.0
    ZOOM_MAX = 5.0
    ZOOM_STEP = 0.25

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cycle: CycleSummary | None = None
        self._bars: list[_BarHit] = []
        self._hovered_index: int | None = None
        self._zoom: float = 1.0

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)

    def set_cycle(self, cycle: CycleSummary | None) -> None:
        self._cycle = cycle
        self._hovered_index = None
        self._zoom = 1.0
        self._recompute_size()
        self.update()

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._recompute_size()
        self.update()

    def _recompute_size(self) -> None:
        if self._cycle is not None and self._cycle.steps:
            rows = len(self._cycle.steps)
            h = rows * (self.BAR_HEIGHT + self.BAR_GAP) + self.HEADER_HEIGHT + 20
            base_w = self.LEFT_PAD + self.RIGHT_PAD + 200
            w = int(base_w * self._zoom)
            self.setMinimumSize(max(400, w), max(220, h))
        else:
            self.setMinimumSize(400, 220)

    # ---- events ---------------------------------------------------------

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

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.pos()
        old = self._hovered_index
        self._hovered_index = None
        for bar in self._bars:
            if bar.rect.contains(pos):
                self._hovered_index = bar.step_index
                QToolTip.showText(
                    self.mapToGlobal(QPoint(pos.x() + 12, pos.y() - 8)),
                    f"{bar.step_index}. {bar.step_name}\n"
                    f"{bar.duration_ms} ms  ({bar.pct:.1f}%)"
                    f"{' — bottleneck' if bar.is_bottleneck else ''}",
                    self,
                )
                break
        if old != self._hovered_index:
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hovered_index is not None:
            self._hovered_index = None
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._cycle is None:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self.ZOOM_MAX, self._zoom + self.ZOOM_STEP)
        elif delta < 0:
            self._zoom = max(self.ZOOM_MIN, self._zoom - self.ZOOM_STEP)
        self._recompute_size()
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_0:
            self.reset_zoom()
        else:
            super().keyPressEvent(event)

    # ---- drawing --------------------------------------------------------

    def _draw_empty(self, painter: QPainter) -> None:
        painter.setPen(self.TEXT_COLOR)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No cycle data yet — start a machine and wait for the first cycle.",
        )
        self._bars.clear()

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
        zoom_label = f"  ({self._zoom:.0f}x)" if self._zoom > 1.0 else ""
        painter.drawText(
            10,
            22,
            f"{cycle.machine_id} — cycle #{cycle.cycle_id}  ·  total {total} ms{zoom_label}",
        )
        painter.setFont(font)

        # Step bars
        self._bars.clear()
        cursor_ms = 0
        y = self.HEADER_HEIGHT
        for step in cycle.steps:
            x = plot_left + int(plot_width * (cursor_ms / total))
            w = max(2, int(plot_width * (step.duration_ms / total)))
            pct = step.duration_ms / total * 100.0

            is_bottleneck = (
                cycle.bottleneck_step_index is not None
                and step.index == cycle.bottleneck_step_index
            )
            is_hovered = step.index == self._hovered_index

            bar_rect = QRect(x, y, w, self.BAR_HEIGHT)
            self._bars.append(
                _BarHit(
                    step_index=step.index,
                    step_name=step.name,
                    duration_ms=step.duration_ms,
                    pct=pct,
                    is_bottleneck=is_bottleneck,
                    rect=bar_rect,
                )
            )

            # Pick color
            if is_bottleneck:
                color = self.BOTTLENECK_HOVER if is_hovered else self.BOTTLENECK_COLOR
            else:
                color = self.HOVER_COLOR if is_hovered else self.NORMAL_COLOR

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
            painter.drawRoundedRect(bar_rect, 4, 4)

            # ms + % label
            painter.setPen(self.TEXT_COLOR)
            painter.drawText(
                QRect(plot_right + 4, y, self.RIGHT_PAD - 8, self.BAR_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{step.duration_ms} ms ({pct:.0f}%)",
            )

            cursor_ms += step.duration_ms
            y += self.BAR_HEIGHT + self.BAR_GAP

        # Plot border
        painter.setPen(QPen(self.GRID_COLOR))
        painter.drawLine(plot_left, self.HEADER_HEIGHT - 4, plot_left, y)
        painter.drawLine(plot_right, self.HEADER_HEIGHT - 4, plot_right, y)


class CycleGanttWidget(QWidget):
    """Gantt + status caption — fetches the latest cycle on `set_machine()`.

    The canvas sits inside a QScrollArea so horizontal zoom works.
    """

    def __init__(self, api: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._machine_id: str | None = None

        layout = QVBoxLayout(self)
        self._caption = QLabel("Select a machine to view its latest cycle.")
        layout.addWidget(self._caption)

        self._canvas = _GanttCanvas()
        self._scroll = QScrollArea(self)
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self._scroll, stretch=1)

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
        """WS push hook — accepts `cycle_summary` payload from CycleProcessor."""
        if not cycle_data or "steps" not in cycle_data:
            return
        from ui.api_client import CycleSummary, StepSummary

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
            max_cv_pct=cycle_data.get("max_cv_pct"),
        )
        self._canvas.set_cycle(cycle)
