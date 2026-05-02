"""OEE Processor tests — Pillar 2 (rolling window A x P x Q)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.data_bus import MachineDataBus
from core.data_model import (
    CycleLog,
    CycleStatus,
    DataBusEvent,
    OEESnapshot,
    StepLog,
    StepStatus,
)
from core.oee_processor import OEEProcessor


def _cycle(
    cycle_id: int,
    duration_ms: float,
    status: CycleStatus = CycleStatus.COMPLETED,
    machine_id: str = "m1",
) -> CycleLog:
    start = datetime.now(timezone.utc)
    end = start + timedelta(milliseconds=duration_ms)
    return CycleLog(
        cycle_id=cycle_id,
        machine_id=machine_id,
        timestamp_start=start,
        timestamp_end=end,
        steps=[
            StepLog(
                step_index=1,
                step_name="A",
                timestamp_start=start,
                timestamp_end=end,
                duration_ms=duration_ms,
                status=StepStatus.COMPLETED,
            )
        ],
        total_duration_ms=duration_ms,
        status=status,
    )


def _evt(cycle: CycleLog) -> DataBusEvent:
    return DataBusEvent(
        machine_id=cycle.machine_id,
        event_type="cycle_complete",
        timestamp=cycle.timestamp_end,
        payload={"cycle_log": cycle},
    )


def test_compute_oee_perfect_run():
    """All cycles completed at ideal speed, no aborts -> OEE = 1.0."""
    now = datetime.now(timezone.utc)
    snap = OEESnapshot.compute(
        machine_id="m1",
        window_start=now - timedelta(hours=1),
        window_end=now,
        cycles_completed=100,
        cycles_aborted=0,
        # 100 cycles at ideal 36s each = 3600s = full hour run time.
        run_time_ms=100 * 36_000,
        ideal_cycle_ms=36_000,
    )
    assert snap.availability == pytest.approx(1.0)
    assert snap.performance == pytest.approx(1.0)
    assert snap.quality == pytest.approx(1.0)
    assert snap.oee == pytest.approx(1.0)


def test_compute_oee_quality_drop():
    now = datetime.now(timezone.utc)
    snap = OEESnapshot.compute(
        machine_id="m1",
        window_start=now - timedelta(hours=1),
        window_end=now,
        cycles_completed=90,
        cycles_aborted=10,
        run_time_ms=100 * 36_000,
        ideal_cycle_ms=36_000,
    )
    assert snap.quality == pytest.approx(0.9)
    # availability stays 1.0; performance is for completed only.
    assert snap.oee == pytest.approx(0.9 * 0.9)  # P also drops a bit (90/100)


def test_compute_oee_with_no_data():
    now = datetime.now(timezone.utc)
    snap = OEESnapshot.compute(
        machine_id="m1",
        window_start=now - timedelta(hours=1),
        window_end=now,
        cycles_completed=0,
        cycles_aborted=0,
        run_time_ms=0.0,
        ideal_cycle_ms=1000.0,
    )
    assert snap.availability == 0.0
    assert snap.performance == 0.0
    assert snap.quality == 1.0  # no aborts -> full quality
    assert snap.oee == 0.0


@pytest.mark.asyncio
async def test_processor_accumulates_cycles_in_window():
    bus = MachineDataBus("m1")
    proc = OEEProcessor("m1", bus=bus, storage=None, ideal_cycle_ms=1000.0)
    await proc.start()

    for k in range(5):
        await bus.publish(_evt(_cycle(k + 1, 1000.0)))

    for _ in range(20):
        if proc.cycles_in_window == 5:
            break
        await asyncio.sleep(0.02)

    assert proc.cycles_in_window == 5
    snap = proc.compute_snapshot()
    assert snap.cycles_completed == 5
    assert snap.cycles_aborted == 0
    assert snap.run_time_ms == 5_000.0
    assert snap.quality == 1.0

    await bus.shutdown()


@pytest.mark.asyncio
async def test_processor_emits_oee_update_event():
    bus = MachineDataBus("m1")
    proc = OEEProcessor("m1", bus=bus, storage=None, ideal_cycle_ms=1000.0)
    updates: list[DataBusEvent] = []

    async def collect(evt: DataBusEvent) -> None:
        if evt.event_type == "oee_update":
            updates.append(evt)

    await proc.start()
    await bus.subscribe("collector", collect)

    await bus.publish(_evt(_cycle(1, 1000.0)))

    for _ in range(20):
        if updates:
            break
        await asyncio.sleep(0.02)

    assert len(updates) == 1
    p = updates[0].payload
    assert {"availability", "performance", "quality", "oee"} <= set(p.keys())
    assert p["cycles_completed"] == 1
    assert p["cycles_aborted"] == 0

    await bus.shutdown()


@pytest.mark.asyncio
async def test_processor_aborts_lower_quality():
    bus = MachineDataBus("m1")
    proc = OEEProcessor("m1", bus=bus, storage=None, ideal_cycle_ms=1000.0)
    await proc.start()

    for k in range(8):
        await bus.publish(_evt(_cycle(k + 1, 1000.0, CycleStatus.COMPLETED)))
    for k in range(2):
        await bus.publish(_evt(_cycle(100 + k, 1000.0, CycleStatus.ABORTED)))

    for _ in range(30):
        if proc.cycles_in_window == 10:
            break
        await asyncio.sleep(0.02)

    snap = proc.compute_snapshot()
    assert snap.cycles_completed == 8
    assert snap.cycles_aborted == 2
    assert snap.quality == pytest.approx(0.8)

    await bus.shutdown()
