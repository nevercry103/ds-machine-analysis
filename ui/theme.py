"""Shared color palette for PyQt6 widgets.

Canonical source for UI colors — all widgets import from here.
Aligned with the design system in docs/DS-P005-UI-001_Design_System.md.
"""

from PyQt6.QtGui import QColor


# --- Semantic colors (primary palette) ---
BLUE_500 = QColor("#3b82f6")
BLUE_400 = QColor("#60a5fa")
RED_500 = QColor("#ef4444")
RED_400 = QColor("#f87171")
GREEN_500 = QColor("#22c55e")
YELLOW_500 = QColor("#eab308")
ORANGE_500 = QColor("#f97316")
GRAY_200 = QColor("#e5e7eb")
GRAY_400 = QColor("#9ca3af")
GRAY_800 = QColor("#1f2937")

# --- Severity mapping ---
SEVERITY_COLORS: dict[str, QColor] = {
    "critical": RED_500,
    "error": ORANGE_500,
    "warning": YELLOW_500,
    "info": BLUE_500,
}


def oee_color(value: float) -> QColor:
    """Traffic-light color for a 0-1 OEE/KPI ratio."""
    if value >= 0.85:
        return GREEN_500
    if value >= 0.60:
        return YELLOW_500
    return RED_500


def format_iso_time(iso_str: str, precision: int = 8) -> str:
    """Extract time portion from an ISO datetime string.

    ``precision=8`` gives HH:MM:SS, ``precision=12`` gives HH:MM:SS.mmm.
    """
    if "T" in iso_str:
        return iso_str.split("T")[1][:precision]
    return iso_str
