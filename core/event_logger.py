"""Pillar 3 — Event Logger.

Subscribes to the per-machine Data Bus and persists every actionable
event to the `events` table:

    cycle_anomaly  -> EventLogEntry(category=ANOMALY, severity=WARNING)
    status_change  -> EventLogEntry(category=STATUS,  severity=INFO/WARNING)
    alarm          -> EventLogEntry(category=ALARM,   severity=ERROR)
    downtime_tag   -> EventLogEntry(category=DOWNTIME, severity=INFO)

Operator-as-Sensor: the API exposes `POST /api/machines/{id}/downtime`
which publishes a `downtime_tag` event onto the bus; this processor
catches it and persists. Same path as PLC-raised events — single
source of truth.

Architecture layer: CORE
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from storage.base_storage import BaseStorage
from utils.logger import log

from .data_bus import MachineDataBus
from .data_model import (
    DataBusEvent,
    DOWNTIME_REASONS,
    EventCategory,
    EventLogEntry,
    EventSeverity,
)


_SEVERITY_BY_TYPE: Mapping[str, EventSeverity] = {
    "cycle_anomaly": EventSeverity.WARNING,
    "alarm": EventSeverity.ERROR,
    "status_change": EventSeverity.INFO,
    "downtime_tag": EventSeverity.INFO,
}


class EventLogger:
    """Per-machine Pillar 3 processor — alarm + anomaly + downtime log."""

    LISTEN_EVENT_TYPES = {
        "cycle_anomaly",
        "alarm",
        "status_change",
        "downtime_tag",
    }

    def __init__(
        self,
        machine_id: str,
        bus: MachineDataBus,
        storage: BaseStorage | None = None,
    ) -> None:
        self.machine_id = machine_id
        self.bus = bus
        self.storage = storage
        self._count = 0
        log.info("EventLogger initialized", machine_id=machine_id)

    # ---- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        await self.bus.subscribe(f"events_{self.machine_id}", self._on_event)

    async def stop(self) -> None:
        await self.bus.unsubscribe(f"events_{self.machine_id}")

    # ---- event handler ------------------------------------------------------

    async def _on_event(self, event: DataBusEvent) -> None:
        if event.event_type not in self.LISTEN_EVENT_TYPES:
            return

        severity = _SEVERITY_BY_TYPE.get(event.event_type, EventSeverity.INFO)
        category = self._category_for(event.event_type)
        message, code = self._summarize(event.event_type, event.payload)

        # Status changes carry a `status` value in payload — escalate to
        # WARNING when the machine entered FAULT.
        if event.event_type == "status_change":
            if str(event.payload.get("status", "")).lower() == "fault":
                severity = EventSeverity.WARNING

        entry = EventLogEntry(
            machine_id=self.machine_id,
            timestamp=event.timestamp or datetime.now(timezone.utc),
            severity=severity,
            category=category,
            code=code,
            message=message,
            payload=dict(event.payload),
        )

        if self.storage is not None:
            try:
                entry = await self.storage.save_event(entry)
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "Failed to persist event",
                    machine_id=self.machine_id,
                    error=str(exc),
                )
                return

        self._count += 1
        log.info(
            "Event logged",
            machine_id=self.machine_id,
            severity=severity.value,
            category=category.value,
            code=code,
        )

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _category_for(event_type: str) -> EventCategory:
        if event_type == "cycle_anomaly":
            return EventCategory.ANOMALY
        if event_type == "alarm":
            return EventCategory.ALARM
        if event_type == "status_change":
            return EventCategory.STATUS
        if event_type == "downtime_tag":
            return EventCategory.DOWNTIME
        return EventCategory.INFO

    @staticmethod
    def _summarize(event_type: str, payload: dict) -> tuple[str, str]:
        """Build (message, code) for a wire event."""
        if event_type == "cycle_anomaly":
            step = payload.get("step_name", "(unknown step)")
            cv = payload.get("cv_pct", 0.0)
            thr = payload.get("threshold_pct", 0.0)
            return (
                f"Cycle Variance anomaly on '{step}': CV%={cv:.1f} (threshold {thr:.1f})",
                "VARIANCE_HIGH",
            )
        if event_type == "alarm":
            code = str(payload.get("code", "ALARM"))
            return (str(payload.get("message", code)), code)
        if event_type == "status_change":
            old = payload.get("old", "?")
            new = payload.get("status", payload.get("new", "?"))
            return (f"Status change: {old} -> {new}", "STATUS_CHANGE")
        if event_type == "downtime_tag":
            reason = payload.get("reason", "unknown")
            note = payload.get("note", "")
            who = payload.get("by", "operator")
            msg = f"Downtime tagged by {who}: {reason}"
            if note:
                msg += f" ({note})"
            return (msg, f"DOWNTIME_{reason.upper()}")
        return (event_type, "")

    @property
    def count(self) -> int:
        return self._count


def is_known_downtime_reason(reason: str) -> bool:
    """Validate a downtime reason against the standard taxonomy."""
    return reason.strip().lower() in DOWNTIME_REASONS
