"""Cycle anomaly tests — F-003 Cycle Variance threshold detection."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.cycle_processor import CycleProcessor
from core.data_bus import MachineDataBus
from core.data_model import CycleLog, CycleStatus, DataBusEvent, StepLog, StepStatus


def _make_cycle(cycle_id: int, durations_ms: list[float]) -> CycleLog:
    start = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
    cursor = start
    steps: list[StepLog] = []
    for k, dur in enumerate(durations_ms):
        end = cursor + timedelta(milliseconds=dur)
        steps.append(
            StepLog(
                step_index=k + 1,
                step_name=f"Step {k + 1}",
                timestamp_start=cursor,
                timestamp_end=end,
                duration_ms=dur,
                status=StepStatus.COMPLETED,
            )
        )
        cursor = end
    return CycleLog(
        cycle_id=cycle_id,
        machine_id="m1",
        timestamp_start=start,
        timestamp_end=cursor,
        steps=steps,
        total_duration_ms=sum(durations_ms),
        status=CycleStatus.COMPLETED,
    )


def _evt(cycle: CycleLog) -> DataBusEvent:
    return DataBusEvent(
        machine_id=cycle.machine_id,
        event_type="cycle_complete",
        timestamp=cycle.timestamp_end,
        payload={"cycle_log": cycle},
    )


@pytest.mark.asyncio
async def test_anomaly_fires_once_when_cv_crosses_threshold():
    bus = MachineDataBus("m1")
    # Low threshold + low min_samples for a fast deterministic test.
    proc = CycleProcessor("m1", bus=bus, storage=None, anomaly_threshold_pct=5.0)
    proc.ANOMALY_MIN_SAMPLES = 3

    anomalies: list[DataBusEvent] = []

    async def collect(evt: DataBusEvent) -> None:
        if evt.event_type == "cycle_anomaly":
            anomalies.append(evt)

    await proc.start()
    await bus.subscribe("collector", collect)

    # 5 samples for step 1 with high variance: mean ~100, big swings.
    high_var = [50.0, 150.0, 60.0, 140.0, 100.0]
    for k, d in enumerate(high_var):
        await bus.publish(_evt(_make_cycle(k + 1, [d])))

    # Drain
    for _ in range(40):
        if anomalies:
            break
        await asyncio.sleep(0.02)

    assert len(anomalies) == 1, f"expected exactly 1 anomaly, got {len(anomalies)}"
    p = anomalies[0].payload
    assert p["step_index"] == 1
    assert p["cv_pct"] >= 5.0
    assert p["samples"] >= 3

    # Push more samples that keep CV high — anomaly must NOT fire again
    # (latched) because the step is already flagged.
    for k, d in enumerate([50.0, 150.0]):
        await bus.publish(_evt(_make_cycle(k + 100, [d])))
    await asyncio.sleep(0.1)
    assert len(anomalies) == 1

    await bus.shutdown()


@pytest.mark.asyncio
async def test_anomaly_does_not_fire_below_min_samples():
    """Even with extreme variance, fewer than MIN_SAMPLES = no anomaly."""
    bus = MachineDataBus("m1")
    proc = CycleProcessor("m1", bus=bus, storage=None, anomaly_threshold_pct=5.0)
    proc.ANOMALY_MIN_SAMPLES = 10  # raise so 2 samples isn't enough

    anomalies: list[DataBusEvent] = []

    async def collect(evt: DataBusEvent) -> None:
        if evt.event_type == "cycle_anomaly":
            anomalies.append(evt)

    await proc.start()
    await bus.subscribe("collector", collect)

    # 2 samples — way under threshold of 10.
    await bus.publish(_evt(_make_cycle(1, [10.0])))
    await bus.publish(_evt(_make_cycle(2, [1000.0])))
    await asyncio.sleep(0.1)

    assert anomalies == []
    await bus.shutdown()


@pytest.mark.asyncio
async def test_anomaly_does_not_fire_when_cv_below_threshold():
    bus = MachineDataBus("m1")
    proc = CycleProcessor("m1", bus=bus, storage=None, anomaly_threshold_pct=20.0)
    proc.ANOMALY_MIN_SAMPLES = 3

    anomalies: list[DataBusEvent] = []

    async def collect(evt: DataBusEvent) -> None:
        if evt.event_type == "cycle_anomaly":
            anomalies.append(evt)

    await proc.start()
    await bus.subscribe("collector", collect)

    # Tight spread around 100ms - CV% should be ~1-2%, well below 20%.
    for k, d in enumerate([100.0, 101.0, 99.0, 100.0, 102.0]):
        await bus.publish(_evt(_make_cycle(k + 1, [d])))
    await asyncio.sleep(0.1)

    assert anomalies == []
    await bus.shutdown()
