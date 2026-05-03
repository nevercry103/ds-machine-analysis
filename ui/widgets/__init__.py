"""
ds_machine_analyzer/ui/widgets/__init__.py
"""

from .cycle_gantt import CycleGanttWidget
from .event_log_view import EventLogWidget
from .machine_manager import MachineManagerWidget
from .oee_dashboard import OEEDashboardWidget

__all__ = [
    "CycleGanttWidget",
    "EventLogWidget",
    "MachineManagerWidget",
    "OEEDashboardWidget",
]
