"""Cycle Processor tests — variance calculation, bottleneck, persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.cycle_processor import CycleProcessor
from core.data_bus import MachineDataBus
from core.data_model import CycleLog, CycleStatus, DataBusEvent, StepLog, StepStatus


def _make_cycle(cycle_id: int, step_durations_ms: list[float]) -> CycleLog:
    """Build a CycleLog with the requested per-step durations."""
    start = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
    cursor = start
    steps: list[StepLog] = []
    for k, dur in enumerate(step_durations_ms):
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
        total_duration_ms=sum(step_durations_ms),
        status=CycleStatus.COMPLETED,
    )


def _cycle_event(cycle: CycleLog) -> DataBusEvent:
    return DataBusEvent(
        machine_id=cycle.machine_id,
        event_type="cycle_complete",
        timestamp=cycle.timestamp_end,
        payload={"cycle_log": cycle},
    )


@pytest.mark.asyncio
async def test_variance_after_n_cycles():
    """After 5 cycles, stdev_ms and cv_pct must be > 0 for a noisy step."""
    bus = MachineDataBus("m1")
    proc = CycleProcessor("m1", bus=bus, storage=None)
    await proc.start()

    # Step 1 fixed at 100ms (variance 0); Step 2 jitters
    samples_step2 = [200.0, 220.0, 180.0, 250.0, 210.0]
    for k, s2 in enumerate(samples_step2):
        await bus.publish(_cycle_event(_make_cycle(k + 1, [100.0, s2])))

    # Let the worker drain
    for _ in range(20):
        if proc.cycle_count == len(samples_step2):
            break
        await asyncio.sleep(0.02)

    assert proc.cycle_count == len(samples_step2)
    stats_by_idx = {s.step_index: s for s in proc.step_stats}

    s1 = stats_by_idx[1]
    s2 = stats_by_idx[2]
    assert s1.count == len(samples_step2)
    assert s1.stdev_ms == pytest.approx(0.0, abs=1e-9)
    assert s1.cv_pct == pytest.approx(0.0, abs=1e-9)

    assert s2.count == len(samples_step2)
    assert s2.stdev_ms > 0
    assert s2.cv_pct > 0
    # mean of [200, 220, 180, 250, 210] = 212
    assert s2.avg_ms == pytest.approx(212.0)

    await bus.shutdown()


@pytest.mark.asyncio
async def test_bottleneck_identification_via_summary_event():
    """Cycle Processor should emit cycle_summary with bottleneck_step set."""
    bus = MachineDataBus("m1")
    proc = CycleProcessor("m1", bus=bus, storage=None)
    summaries: list[DataBusEvent] = []

    async def collect(evt: DataBusEvent) -> None:
        if evt.event_type == "cycle_summary":
            summaries.append(evt)

    await proc.start()
    await bus.subscribe("collector", collect)

    # Step 3 is clearly the bottleneck
    await bus.publish(_cycle_event(_make_cycle(1, [100.0, 200.0, 800.0, 150.0])))

    for _ in range(20):
        if summaries:
            break
        await asyncio.sleep(0.02)

    assert len(summaries) == 1
    payload = summaries[0].payload
    assert payload["bottleneck_step_index"] == 3
    assert payload["total_ms"] == 1250.0
    assert payload["step_count"] == 4

    await bus.shutdown()


@pytest.mark.asyncio
async def test_processor_ignores_non_cycle_events():
    bus = MachineDataBus("m1")
    proc = CycleProcessor("m1", bus=bus, storage=None)
    await proc.start()

    # Wrong event type — should not be counted
    await bus.publish(
        DataBusEvent(
            machine_id="m1",
            event_type="alarm",
            timestamp=datetime.now(timezone.utc),
            payload={},
        )
    )
    await asyncio.sleep(0.05)
    assert proc.cycle_count == 0

    await bus.shutdown()
