"""Machine Data Bus — per-pillar pub/sub event stream.

One DataBus per machine. Each subscriber gets its own asyncio.Queue, so
a slow pillar (e.g. OEE writer) cannot backpressure cycle capture.

Architecture rule (F-001 + roadmap §4):
    Adapter publishes events to bus.
    Bus fans out to N subscribers, each consuming from its own queue.
    Subscribers run their own dispatch task.

Lifecycle:
    bus = MachineDataBus("machine_001")
    queue = bus.subscribe("cycle_processor")  # caller starts a worker on queue
    await bus.publish(event)                  # non-blocking, never raises
    bus.unsubscribe("cycle_processor")        # clean shutdown
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from utils.logger import log

from .data_model import DataBusEvent

EventCallback = Callable[[DataBusEvent], Awaitable[None]]


@dataclass
class _Subscriber:
    name: str
    queue: asyncio.Queue[DataBusEvent]
    task: asyncio.Task[None] | None = None


class MachineDataBus:
    """Per-machine pub/sub bus with one queue per subscriber.

    Designed so that one slow consumer cannot stall fast consumers. Each
    publish is O(N_subscribers) `queue.put_nowait()` calls — bounded
    queues drop oldest events on overflow rather than block the publisher.
    """

    DEFAULT_QUEUE_SIZE = 1000

    def __init__(self, machine_id: str, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self.machine_id = machine_id
        self._queue_size = queue_size
        self._subscribers: dict[str, _Subscriber] = {}
        self._lock = asyncio.Lock()
        log.info("DataBus initialized", machine_id=machine_id)

    async def subscribe(
        self,
        name: str,
        callback: EventCallback | None = None,
    ) -> asyncio.Queue[DataBusEvent]:
        """Register a subscriber and return its dedicated queue.

        If `callback` is provided, the bus starts a worker task that
        consumes from the queue and invokes the callback for each event.
        Otherwise the caller is responsible for draining the queue.
        """
        async with self._lock:
            if name in self._subscribers:
                raise ValueError(f"Subscriber '{name}' already registered")

            queue: asyncio.Queue[DataBusEvent] = asyncio.Queue(maxsize=self._queue_size)
            sub = _Subscriber(name=name, queue=queue)

            if callback is not None:
                sub.task = asyncio.create_task(
                    self._run_worker(name, queue, callback),
                    name=f"databus.{self.machine_id}.{name}",
                )

            self._subscribers[name] = sub
            log.info("DataBus subscribe", machine_id=self.machine_id, subscriber=name)
            return queue

    async def unsubscribe(self, name: str) -> None:
        async with self._lock:
            sub = self._subscribers.pop(name, None)

        if sub is None:
            return

        if sub.task is not None:
            sub.task.cancel()
            try:
                await sub.task
            except (asyncio.CancelledError, Exception):
                pass

        log.info("DataBus unsubscribe", machine_id=self.machine_id, subscriber=name)

    async def publish(self, event: DataBusEvent) -> None:
        """Fan-out event to every subscriber's queue.

        Never blocks the publisher: full queues drop the oldest event and
        log a warning. This protects the cycle-capture path from a slow
        consumer (the whole reason for per-pillar queues).
        """
        for sub in list(self._subscribers.values()):
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest, retry once.
                try:
                    sub.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass
                log.warning(
                    "DataBus queue full, dropped event",
                    machine_id=self.machine_id,
                    subscriber=sub.name,
                    event_type=event.event_type,
                )

    async def shutdown(self) -> None:
        """Cancel all worker tasks; idempotent."""
        for name in list(self._subscribers.keys()):
            await self.unsubscribe(name)

    @property
    def subscriber_names(self) -> list[str]:
        return list(self._subscribers.keys())

    async def _run_worker(
        self,
        name: str,
        queue: asyncio.Queue[DataBusEvent],
        callback: EventCallback,
    ) -> None:
        while True:
            event = await queue.get()
            try:
                await callback(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception(
                    "DataBus subscriber raised",
                    machine_id=self.machine_id,
                    subscriber=name,
                    error=str(exc),
                )
            finally:
                queue.task_done()
