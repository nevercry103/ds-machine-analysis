"""Pillar 2 — OEE Processor.

Rolling-window OEE calculator. Subscribes to the per-machine Data Bus,
listens for `cycle_complete` events, and maintains a deque of recent
cycles trimmed to the configured window. Snapshot is recomputed and
persisted on every cycle.

Definitions (matches `OEESnapshot.compute`):
    Availability = run_time_ms / planned_time_ms
    Performance  = (cycles_completed * ideal_cycle_ms) / run_time_ms
    Quality      = cycles_completed / (cycles_completed + cycles_aborted)
    OEE          = A * P * Q

Architecture layer: CORE
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque

from storage.base_storage import BaseStorage
from utils.logger import log

from .data_bus import MachineDataBus
from .data_model import (
    CycleLog,
    CycleStatus,
    DataBusEvent,
    OEESnapshot,
)


class OEEProcessor:
    """Per-machine Pillar 2 processor — rolling-window OEE."""

    DEFAULT_WINDOW_MIN = 60        # 60-minute rolling window
    DEFAULT_IDEAL_CYCLE_MS = 0.0   # 0 = fall back to rolling minimum

    def __init__(
        self,
        machine_id: str,
        bus: MachineDataBus,
        storage: BaseStorage | None = None,
        *,
        window_minutes: int = DEFAULT_WINDOW_MIN,
        ideal_cycle_ms: float = DEFAULT_IDEAL_CYCLE_MS,
    ) -> None:
        self.machine_id = machine_id
        self.bus = bus
        self.storage = storage
        self.window = timedelta(minutes=window_minutes)
        self._configured_ideal_ms = ideal_cycle_ms

        # Rolling buffer: (cycle_end_dt, total_duration_ms, status).
        self._cycles: Deque[tuple[datetime, float, CycleStatus]] = deque()
        self._last_snapshot: OEESnapshot | None = None

        log.info(
            "OEEProcessor initialized",
            machine_id=machine_id,
            window_min=window_minutes,
            ideal_ms=ideal_cycle_ms,
        )

    # ---- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        await self.bus.subscribe(f"oee_{self.machine_id}", self._on_event)

    async def stop(self) -> None:
        await self.bus.unsubscribe(f"oee_{self.machine_id}")

    # ---- event handler ------------------------------------------------------

    async def _on_event(self, event: DataBusEvent) -> None:
        if event.event_type != "cycle_complete":
            return

        cycle: CycleLog | None = event.payload.get("cycle_log")
        if cycle is None:
            return

        self._record(cycle)
        snapshot = self.compute_snapshot()
        self._last_snapshot = snapshot

        if self.storage is not None:
            try:
                await self.storage.save_oee_snapshot(snapshot)
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "Failed to persist OEE snapshot",
                    machine_id=self.machine_id,
                    error=str(exc),
                )

        await self.bus.publish(
            DataBusEvent(
                machine_id=self.machine_id,
                event_type="oee_update",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "availability": round(snapshot.availability, 4),
                    "performance": round(snapshot.performance, 4),
                    "quality": round(snapshot.quality, 4),
                    "oee": round(snapshot.oee, 4),
                    "cycles_completed": snapshot.cycles_completed,
                    "cycles_aborted": snapshot.cycles_aborted,
                    "window_minutes": int(self.window.total_seconds() // 60),
                },
            )
        )

    # ---- core math ---------------------------------------------------------

    def _record(self, cycle: CycleLog) -> None:
        self._cycles.append(
            (cycle.timestamp_end, cycle.total_duration_ms, cycle.status)
        )
        self._trim_window()

    def _trim_window(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.window
        # Window edges are timezone-aware; cycle.timestamp_end may be
        # naive depending on the upstream adapter — compare safely.
        while self._cycles:
            ts, _, _ = self._cycles[0]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                self._cycles.popleft()
            else:
                break

    def _ideal_cycle_ms(self) -> float:
        """Return the configured ideal cycle time, or rolling minimum
        if not configured. Rolling minimum is conservative — actual
        ideal should be set per-machine in the YAML once measured.
        """
        if self._configured_ideal_ms > 0:
            return self._configured_ideal_ms
        if not self._cycles:
            return 0.0
        return min(d for _, d, _ in self._cycles)

    def compute_snapshot(self) -> OEESnapshot:
        now = datetime.now(timezone.utc)
        window_start = now - self.window

        completed = sum(1 for _, _, s in self._cycles if s == CycleStatus.COMPLETED)
        aborted = sum(1 for _, _, s in self._cycles if s == CycleStatus.ABORTED)
        run_time_ms = sum(
            d for _, d, s in self._cycles if s == CycleStatus.COMPLETED
        )

        return OEESnapshot.compute(
            machine_id=self.machine_id,
            window_start=window_start,
            window_end=now,
            cycles_completed=completed,
            cycles_aborted=aborted,
            run_time_ms=run_time_ms,
            ideal_cycle_ms=self._ideal_cycle_ms(),
        )

    # ---- accessors ---------------------------------------------------------

    @property
    def last_snapshot(self) -> OEESnapshot | None:
        return self._last_snapshot

    @property
    def cycles_in_window(self) -> int:
        self._trim_window()
        return len(self._cycles)
