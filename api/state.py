"""Shared FastAPI app state — registry + storage + WS broadcast hub."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.machine_registry import MachineRegistry
from storage.base_storage import BaseStorage


@dataclass
class WSHub:
    """Per-machine WebSocket fan-out — registers connected clients and
    forwards Data Bus events to them.

    Created during `MachineRegistry.start_all()`; one bus subscription
    per machine. The hub is intentionally simple: queue per client, drop
    on overflow rather than block the bus.
    """

    clients: dict[str, set[asyncio.Queue]] = field(default_factory=dict)

    def add_client(self, machine_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.clients.setdefault(machine_id, set()).add(queue)
        return queue

    def remove_client(self, machine_id: str, queue: asyncio.Queue) -> None:
        if machine_id in self.clients:
            self.clients[machine_id].discard(queue)
            if not self.clients[machine_id]:
                del self.clients[machine_id]

    async def broadcast(self, machine_id: str, message: dict) -> None:
        for queue in list(self.clients.get(machine_id, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Slow client — drop oldest, retry once.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass


@dataclass
class AppState:
    registry: MachineRegistry
    storage: BaseStorage
    ws_hub: WSHub = field(default_factory=WSHub)
