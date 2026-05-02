"""Abstract protocol adapter base class.

Every protocol adapter (OPC-UA / Modbus / EtherNet-IP / ADS / MC / FINS)
inherits from `BaseProtocolAdapter`. The adapter is **stateless** — it
detects the PLC handshake, reads cycle data, publishes to the per-machine
Data Bus, and acknowledges. All business logic stays in `core/`.

Architecture layer: PROTOCOL LAYER
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.data_bus import MachineDataBus
from core.data_model import MachineConfig, MachineStatus
from utils.logger import log


class BaseProtocolAdapter(ABC):
    """Abstract base for all protocol adapters.

    Subclasses implement the connect/handshake loop. The base class owns
    the lifecycle (start/stop), status reporting, and Data Bus handle.
    """

    def __init__(self, config: MachineConfig, bus: MachineDataBus) -> None:
        self.config = config
        self.bus = bus
        self.machine_id = config.machine_id
        self._status: MachineStatus = MachineStatus.OFFLINE
        log.info(
            "Adapter created",
            machine_id=self.machine_id,
            adapter=self.__class__.__name__,
            url=config.protocol.url,
        )

    # ---- lifecycle ----------------------------------------------------------

    @abstractmethod
    async def start(self, *, initial_cycle_id: int = 0) -> None:
        """Start the adapter loop (connect + poll + publish).

        ``initial_cycle_id`` is the highest cycle_id already persisted
        for this machine (queried by `MachineRegistry` from storage).
        Adapters use it to seed their internal counter so they resume
        from where the previous process left off, avoiding
        UNIQUE(machine_id, cycle_id) collisions on restart.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter loop and release the connection."""

    # ---- status -------------------------------------------------------------

    @property
    def status(self) -> MachineStatus:
        return self._status

    def _set_status(self, status: MachineStatus) -> None:
        if self._status != status:
            log.info(
                "Adapter status change",
                machine_id=self.machine_id,
                old=self._status.value,
                new=status.value,
            )
        self._status = status

    # ---- raw read/write hooks (optional for some adapters) ------------------

    async def read_variable(self, tag_name: str) -> Any:
        raise NotImplementedError

    async def write_variable(self, tag_name: str, value: Any) -> bool:
        raise NotImplementedError
