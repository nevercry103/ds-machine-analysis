"""Cycle Processor — Pillar 1 engine.

Subscribes to the per-machine Data Bus, processes `cycle_complete` events:
    - persists the cycle to storage
    - updates rolling step stats (Welford's algorithm in CycleStats)
    - computes Cycle Variance (sigma + CV%) — the headline KPI per F-003
    - publishes a `cycle_summary` event back to the bus for downstream
      WebSocket fan-out

Architecture layer: CORE
"""

from __future__ import annotations

from datetime import datetime, timezone

from storage.base_storage import BaseStorage
from utils.logger import log

from .data_bus import MachineDataBus
from .data_model import CycleLog, CycleStats, DataBusEvent


class CycleProcessor:
    """Per-machine Pillar 1 processor."""

    # F-003: emit `cycle_anomaly` when a step's CV% climbs above this
    # threshold AND there are at least MIN_SAMPLES baseline cycles.
    # 8% CV% is a conservative starting baseline for industrial
    # processes; tuned per pack/customer over time.
    ANOMALY_CV_PCT_THRESHOLD = 8.0
    ANOMALY_MIN_SAMPLES = 10

    def __init__(
        self,
        machine_id: str,
        bus: MachineDataBus,
        storage: BaseStorage | None = None,
        anomaly_threshold_pct: float | None = None,
    ) -> None:
        self.machine_id = machine_id
        self.bus = bus
        self.storage = storage
        self.anomaly_threshold_pct = (
            anomaly_threshold_pct
            if anomaly_threshold_pct is not None
            else self.ANOMALY_CV_PCT_THRESHOLD
        )

        self._step_stats: dict[int, CycleStats] = {}
        self._cycle_count = 0
        self._last_total_ms: float = 0.0
        self._last_cycle_id: int = 0
        # Steps that already emitted an anomaly — avoid spamming the bus
        # for every cycle once the threshold is crossed.
        self._anomalous_steps: set[int] = set()

        log.info("CycleProcessor initialized", machine_id=machine_id)

    async def start(self) -> None:
        """Subscribe to bus events; begin processing."""
        await self.bus.subscribe("cycle_processor", self._on_event)

    async def stop(self) -> None:
        await self.bus.unsubscribe("cycle_processor")

    async def _on_event(self, event: DataBusEvent) -> None:
        if event.event_type != "cycle_complete":
            return

        cycle: CycleLog | None = event.payload.get("cycle_log")
        if cycle is None:
            log.warning("cycle_complete event missing cycle_log payload")
            return

        self._cycle_count += 1
        self._last_total_ms = cycle.total_duration_ms
        self._last_cycle_id = cycle.cycle_id

        self._update_stats(cycle)
        bottleneck = self._find_bottleneck()

        if self.storage is not None:
            try:
                await self.storage.save_cycle(cycle)
                for stats in self._step_stats.values():
                    await self.storage.save_step_stats(stats)
            except Exception as exc:
                log.exception(
                    "Failed to persist cycle",
                    machine_id=self.machine_id,
                    cycle_id=cycle.cycle_id,
                    error=str(exc),
                )

        await self.bus.publish(
            DataBusEvent(
                machine_id=self.machine_id,
                event_type="cycle_summary",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "cycle_id": cycle.cycle_id,
                    "total_ms": cycle.total_duration_ms,
                    "step_count": len(cycle.steps),
                    "bottleneck_step": bottleneck.step_name if bottleneck else None,
                    "bottleneck_step_ms": bottleneck.avg_ms if bottleneck else None,
                    "bottleneck_step_index": bottleneck.step_index if bottleneck else None,
                    "max_cv_pct": max(
                        (s.cv_pct for s in self._step_stats.values()), default=0.0
                    ),
                    "steps": [
                        {
                            "index": s.step_index,
                            "name": s.step_name,
                            "duration_ms": s.duration_ms,
                            "started_at": s.timestamp_start.isoformat(),
                            "ended_at": s.timestamp_end.isoformat(),
                        }
                        for s in cycle.steps
                    ],
                },
            )
        )

        # F-003: anomaly detection — Cycle Variance is the headline KPI.
        # Emit one event per step when it first crosses the threshold;
        # don't spam the bus for every cycle thereafter.
        for stats in self._step_stats.values():
            if stats.count < self.ANOMALY_MIN_SAMPLES:
                continue
            crossed = stats.cv_pct >= self.anomaly_threshold_pct
            if crossed and stats.step_index not in self._anomalous_steps:
                self._anomalous_steps.add(stats.step_index)
                await self.bus.publish(
                    DataBusEvent(
                        machine_id=self.machine_id,
                        event_type="cycle_anomaly",
                        timestamp=datetime.now(timezone.utc),
                        payload={
                            "step_index": stats.step_index,
                            "step_name": stats.step_name,
                            "cv_pct": round(stats.cv_pct, 2),
                            "stdev_ms": round(stats.stdev_ms, 2),
                            "avg_ms": round(stats.avg_ms, 2),
                            "threshold_pct": self.anomaly_threshold_pct,
                            "samples": stats.count,
                            "cycle_id": cycle.cycle_id,
                        },
                    )
                )
                log.warning(
                    "Cycle variance anomaly detected",
                    machine_id=self.machine_id,
                    step_index=stats.step_index,
                    step_name=stats.step_name,
                    cv_pct=round(stats.cv_pct, 2),
                    threshold_pct=self.anomaly_threshold_pct,
                )
            elif not crossed and stats.step_index in self._anomalous_steps:
                # Recovered — clear the latch so we'll re-fire if it
                # crosses again later.
                self._anomalous_steps.discard(stats.step_index)

        log.info(
            "Cycle processed",
            machine_id=self.machine_id,
            cycle_id=cycle.cycle_id,
            total_ms=cycle.total_duration_ms,
            bottleneck=bottleneck.step_name if bottleneck else None,
            max_cv_pct=round(
                max((s.cv_pct for s in self._step_stats.values()), default=0.0), 2
            ),
        )

    def _update_stats(self, cycle: CycleLog) -> None:
        for step in cycle.steps:
            stats = self._step_stats.get(step.step_index)
            if stats is None:
                stats = CycleStats(
                    machine_id=self.machine_id,
                    step_index=step.step_index,
                    step_name=step.step_name,
                )
                self._step_stats[step.step_index] = stats
            stats.update(step.duration_ms)

    def _find_bottleneck(self) -> CycleStats | None:
        if not self._step_stats:
            return None
        return max(self._step_stats.values(), key=lambda s: s.avg_ms)

    @property
    def step_stats(self) -> list[CycleStats]:
        return sorted(self._step_stats.values(), key=lambda s: s.step_index)

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_total_ms(self) -> float:
        return self._last_total_ms

    @property
    def last_cycle_id(self) -> int:
        return self._last_cycle_id
