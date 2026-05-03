"""OEE Dashboard widget — Pillar 2.

Displays Availability x Performance x Quality gauge and breakdown
for the selected machine. Polls /api/machines/{id}/oee periodically
and refreshes on WS cycle_summary events.

Architecture rule: UI consumes the API only — no direct core imports.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget, QLabel

from ui.api_client import ApiClient, ApiError, OEESnapshot
from utils.logger import log


class _OEEGauge(QWidget):
    """Circular OEE gauge + A/P/Q bar breakdown."""

    GOOD = QColor("#22c55e")   # green-500
    OKAY = QColor("#eab308")   # yellow-500
    BAD = QColor("#ef4444")    # red-500
    TRACK = QColor("#e5e7eb")  # gray-200
    TEXT = QColor("#1f2937")   # gray-800

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap: OEESnapshot | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 320)

    def set_snapshot(self, snap: OEESnapshot | None) -> None:
        self._snap = snap
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), self.palette().window())
            if self._snap is None:
                painter.setPen(self.TEXT)
                painter.drawText(
                    self.rect(), Qt.AlignmentFlag.AlignCenter,
                    "OEE not available — enable oee_analyzer in YAML.",
                )
                return
            self._draw(painter, self._snap)
        finally:
            painter.end()

    def _oee_color(self, value: float) -> QColor:
        if value >= 0.85:
            return self.GOOD
        if value >= 0.60:
            return self.OKAY
        return self.BAD

    def _draw(self, p: QPainter, s: OEESnapshot) -> None:
        w = self.width()

        # --- Arc gauge (top center) ---
        arc_size = min(180, w - 40)
        arc_x = (w - arc_size) // 2
        arc_y = 10
        arc_rect = QRect(arc_x, arc_y, arc_size, arc_size)

        pen_w = 12
        # Track
        p.setPen(QPen(self.TRACK, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(arc_rect, 225 * 16, -270 * 16)

        # Fill
        color = self._oee_color(s.oee)
        p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(-270 * 16 * s.oee)
        p.drawArc(arc_rect, 225 * 16, span)

        # OEE text in center
        bold = QFont(p.font())
        bold.setPointSize(24)
        bold.setBold(True)
        p.setFont(bold)
        p.setPen(self.TEXT)
        p.drawText(
            arc_rect, Qt.AlignmentFlag.AlignCenter,
            f"{s.oee * 100:.1f}%",
        )

        # Label below arc
        small = QFont(p.font())
        small.setPointSize(10)
        small.setBold(False)
        p.setFont(small)
        p.drawText(
            QRect(0, arc_y + arc_size - 5, w, 24),
            Qt.AlignmentFlag.AlignHCenter,
            "OEE",
        )

        # --- A / P / Q bars ---
        bar_top = arc_y + arc_size + 24
        bar_left = 20
        bar_width = w - 40
        bar_h = 18
        gap = 32

        for i, (label, val) in enumerate([
            ("Availability", s.availability),
            ("Performance", s.performance),
            ("Quality", s.quality),
        ]):
            y = bar_top + i * (bar_h + gap)

            # Label
            p.setPen(self.TEXT)
            p.setFont(small)
            p.drawText(bar_left, y - 2, f"{label}  {val * 100:.1f}%")

            # Track
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self.TRACK))
            p.drawRoundedRect(bar_left, y + 2, bar_width, bar_h, 4, 4)

            # Fill
            fill_w = max(0, int(bar_width * val))
            p.setBrush(QBrush(self._oee_color(val)))
            p.drawRoundedRect(bar_left, y + 2, fill_w, bar_h, 4, 4)

        # --- Cycle counts ---
        y = bar_top + 3 * (bar_h + gap) + 8
        p.setPen(self.TEXT)
        p.setFont(small)
        p.drawText(
            bar_left, y,
            f"Cycles: {s.cycles_completed} completed, {s.cycles_aborted} aborted  "
            f"·  Window: {s.window_minutes} min",
        )


class OEEDashboardWidget(QWidget):
    """OEE dashboard — fetches /api/machines/{id}/oee on timer + on demand."""

    def __init__(self, api: ApiClient, parent: QWidget | None = None, refresh_ms: int = 10000) -> None:
        super().__init__(parent)
        self._api = api
        self._machine_id: str | None = None

        layout = QVBoxLayout(self)
        self._caption = QLabel("Select a machine to view OEE.")
        layout.addWidget(self._caption)

        self._gauge = _OEEGauge(self)
        layout.addWidget(self._gauge, stretch=1)

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
            snap = self._api.get_oee(self._machine_id)
            self._caption.setText(
                f"{self._machine_id} — OEE {snap.oee * 100:.1f}%  "
                f"(A={snap.availability * 100:.0f}% P={snap.performance * 100:.0f}% "
                f"Q={snap.quality * 100:.0f}%)"
            )
            self._gauge.set_snapshot(snap)
        except ApiError as exc:
            if exc.status == 409:
                self._caption.setText(f"{self._machine_id}: OEE not enabled")
                self._gauge.set_snapshot(None)
                self._timer.stop()
            else:
                self._caption.setText(f"OEE error — {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(event)
