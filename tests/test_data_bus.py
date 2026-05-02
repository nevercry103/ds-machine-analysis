"""Data Bus tests — per-pillar queues, slow consumer isolation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from core.data_bus import MachineDataBus
from core.data_model import DataBusEvent


def _event(machine_id: str = "m1", event_type: str = "cycle_complete") -> DataBusEvent:
    return DataBusEvent(
        machine_id=machine_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        payload={"counter": 0},
    )


@pytest.mark.asyncio
async def test_subscribe_and_publish_with_callback():
    bus = MachineDataBus("m1")
    received: list[DataBusEvent] = []

    async def cb(evt: DataBusEvent) -> None:
        received.append(evt)

    await bus.subscribe("test", cb)
    await bus.publish(_event())
    await asyncio.sleep(0.05)  # let worker drain
    await bus.shutdown()

    assert len(received) == 1
    assert received[0].event_type == "cycle_complete"


@pytest.mark.asyncio
async def test_per_pillar_queues_are_isolated():
    """A slow consumer must not stop a fast consumer from receiving events."""
    bus = MachineDataBus("m1")
    fast: list[DataBusEvent] = []
    slow_started = asyncio.Event()
    slow_release = asyncio.Event()

    async def fast_cb(evt: DataBusEvent) -> None:
        fast.append(evt)

    async def slow_cb(evt: DataBusEvent) -> None:
        slow_started.set()
        await slow_release.wait()  # blocks until released

    await bus.subscribe("fast", fast_cb)
    await bus.subscribe("slow", slow_cb)

    for _ in range(10):
        await bus.publish(_event())

    # Wait for slow to be running (so we know dispatch happened)
    await asyncio.wait_for(slow_started.wait(), timeout=1.0)
    await asyncio.sleep(0.1)  # give fast time to drain

    # Fast must have received all 10 events even though slow is still blocked
    assert len(fast) == 10

    slow_release.set()
    await bus.shutdown()


@pytest.mark.asyncio
async def test_unsubscribe_stops_callback():
    bus = MachineDataBus("m1")
    received: list[DataBusEvent] = []

    async def cb(evt: DataBusEvent) -> None:
        received.append(evt)

    await bus.subscribe("test", cb)
    await bus.publish(_event())
    await asyncio.sleep(0.05)
    assert len(received) == 1

    await bus.unsubscribe("test")
    await bus.publish(_event())
    await asyncio.sleep(0.05)
    assert len(received) == 1  # unchanged after unsubscribe

    await bus.shutdown()


@pytest.mark.asyncio
async def test_double_subscribe_raises():
    bus = MachineDataBus("m1")

    async def cb(_: DataBusEvent) -> None:
        return None

    await bus.subscribe("dup", cb)
    with pytest.raises(ValueError):
        await bus.subscribe("dup", cb)

    await bus.shutdown()


@pytest.mark.asyncio
async def test_publish_does_not_block_when_queue_full():
    bus = MachineDataBus("m1", queue_size=2)
    # Subscribe but never drain.
    queue = await bus.subscribe("idle")  # no callback -> caller drains

    # Publish more than queue_size — should not raise, oldest is dropped.
    for _ in range(10):
        await bus.publish(_event())

    # Queue size never exceeds maxsize
    assert queue.qsize() <= 2
    await bus.shutdown()
