"""Machine Registry — manages up to 10 machines per instance.

Owns the lifecycle of every registered machine: data bus, protocol
adapter, cycle processor, and storage handle. The Registry is a long-
lived object held by the FastAPI lifespan and (when present) the PyQt6
main window.

Architecture layer: CORE
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from storage.base_storage import BaseStorage
from utils.logger import log

from .config_model import MachineConfigSchema
from .anomaly_detector import AnomalyDetector
from .cycle_processor import CycleProcessor
from .data_bus import MachineDataBus
from .data_model import MachineConfig, MachineStatus
from .event_logger import EventLogger
from .oee_processor import OEEProcessor
from .tier_profile import TierProfile, validate_machine_requirements


class MachineHandle:
    """All per-machine runtime objects bundled together.

    The registry hands these out so callers (API, UI, tests) have a
    single accessor instead of dict-juggling.
    """

    def __init__(
        self,
        config: MachineConfig,
        bus: MachineDataBus,
        adapter,  # plc.base_adapter.BaseProtocolAdapter (forward ref)
        processor: CycleProcessor,
        oee: OEEProcessor | None = None,
        events: EventLogger | None = None,
        anomaly: AnomalyDetector | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.adapter = adapter
        self.processor = processor
        self.oee = oee
        self.events = events
        self.anomaly = anomaly

    @property
    def machine_id(self) -> str:
        return self.config.machine_id

    @property
    def status(self) -> MachineStatus:
        return self.adapter.status


class MachineRegistry:
    """Central registry — load configs, register machines, run lifecycle."""

    MAX_MACHINES = 10

    def __init__(
        self,
        config_dir: Path | str,
        storage: BaseStorage | None = None,
        tier: TierProfile | None = None,
    ) -> None:
        self.config_dir = Path(config_dir)
        self.storage = storage
        self.tier = tier
        self._handles: dict[str, MachineHandle] = {}
        self._lock = asyncio.Lock()
        log.info(
            "MachineRegistry initialized",
            config_dir=str(self.config_dir),
            tier=tier.tier_id if tier else None,
        )

    # ---- config loading -----------------------------------------------------

    async def load_all_configs(self) -> list[MachineConfig]:
        configs: list[MachineConfig] = []
        for yaml_file in sorted(self.config_dir.glob("machine_*.yaml")):
            schema = await asyncio.to_thread(MachineConfigSchema.from_yaml, yaml_file)
            configs.append(schema.to_machine_config())
            log.info(
                "Loaded machine config",
                machine_id=configs[-1].machine_id,
                path=str(yaml_file),
            )
        return configs

    # ---- registration -------------------------------------------------------

    async def register(self, config: MachineConfig) -> MachineHandle:
        """Register one machine — create bus, adapter, processor.

        When a tier profile is set, validates the machine against the
        tier's capacity + feature flags before doing anything stateful.
        """
        # Local import to avoid circular dependency between core <-> plc.
        from plc import build_adapter

        async with self._lock:
            if len(self._handles) >= self.MAX_MACHINES:
                raise ValueError(
                    f"Cannot register '{config.machine_id}': max {self.MAX_MACHINES} reached"
                )
            if config.machine_id in self._handles:
                raise ValueError(f"Machine '{config.machine_id}' already registered")

            if self.tier is not None:
                # Raises TierError if the machine exceeds the tier limits.
                validate_machine_requirements(
                    self.tier,
                    machine_id=config.machine_id,
                    tier_required=config.tier_required,
                    total_steps=config.total_steps,
                    replay_enabled=config.replay_enabled,
                    current_machine_count=len(self._handles),
                )

            bus = MachineDataBus(config.machine_id)
            adapter = build_adapter(config, bus)
            processor = CycleProcessor(
                machine_id=config.machine_id,
                bus=bus,
                storage=self.storage,
            )

            oee_processor: OEEProcessor | None = None
            if config.oee_enabled and self._tier_allows("oee_analytics"):
                oee_processor = OEEProcessor(
                    machine_id=config.machine_id,
                    bus=bus,
                    storage=self.storage,
                    window_minutes=config.oee_window_minutes,
                    ideal_cycle_ms=config.oee_ideal_cycle_ms,
                )
            elif config.oee_enabled:
                log.warning(
                    "OEE enabled in config but tier does not include oee_analytics",
                    machine_id=config.machine_id,
                    tier=self.tier.tier_id if self.tier else None,
                )

            event_logger: EventLogger | None = None
            if config.event_log_enabled and self._tier_allows("event_log"):
                event_logger = EventLogger(
                    machine_id=config.machine_id,
                    bus=bus,
                    storage=self.storage,
                )
            elif config.event_log_enabled:
                log.warning(
                    "Event log enabled in config but tier does not include event_log",
                    machine_id=config.machine_id,
                    tier=self.tier.tier_id if self.tier else None,
                )

            anomaly_detector = AnomalyDetector(machine_id=config.machine_id)

            handle = MachineHandle(
                config, bus, adapter, processor,
                oee=oee_processor, events=event_logger, anomaly=anomaly_detector,
            )
            self._handles[config.machine_id] = handle
            log.info(
                "Machine registered",
                machine_id=config.machine_id,
                oee=oee_processor is not None,
                events=event_logger is not None,
            )
            return handle

    def _tier_allows(self, feature: str) -> bool:
        """Tier check helper — returns True when no tier loaded (dev mode)."""
        if self.tier is None:
            return True
        return self.tier.has_feature(feature)

    # ---- lifecycle ----------------------------------------------------------

    async def start_all(self) -> None:
        """Subscribe processors and start adapters for every machine.

        Before each adapter starts, query storage for the last persisted
        ``cycle_id`` so the adapter resumes counting from the right
        place. Without this, a fresh process restart against an existing
        DB would emit cycle_id=1 and trip the UNIQUE constraint.
        """
        for handle in self._handles.values():
            await handle.processor.start()
            if handle.oee is not None:
                await handle.oee.start()
            if handle.events is not None:
                await handle.events.start()

            initial_cycle_id = 0
            if self.storage is not None:
                try:
                    initial_cycle_id = await self.storage.get_last_cycle_id(
                        handle.machine_id
                    )
                except Exception as exc:
                    log.warning(
                        "Could not seed cycle counter from storage",
                        machine_id=handle.machine_id,
                        error=str(exc),
                    )
            if initial_cycle_id > 0:
                log.info(
                    "Resuming cycle counter from storage",
                    machine_id=handle.machine_id,
                    initial_cycle_id=initial_cycle_id,
                )
            await handle.adapter.start(initial_cycle_id=initial_cycle_id)
        log.info("Registry started", count=len(self._handles))

    async def stop_all(self) -> None:
        """Stop adapters first (no new events), then drain processors."""
        for handle in self._handles.values():
            try:
                await handle.adapter.stop()
            except Exception as exc:
                log.warning(
                    "Adapter stop failed",
                    machine_id=handle.machine_id,
                    error=str(exc),
                )
        for handle in self._handles.values():
            try:
                await handle.processor.stop()
                if handle.oee is not None:
                    await handle.oee.stop()
                if handle.events is not None:
                    await handle.events.stop()
                await handle.bus.shutdown()
            except Exception as exc:
                log.warning(
                    "Processor/bus stop failed",
                    machine_id=handle.machine_id,
                    error=str(exc),
                )
        log.info("Registry stopped")

    # ---- accessors ----------------------------------------------------------

    def get(self, machine_id: str) -> MachineHandle | None:
        return self._handles.get(machine_id)

    def all(self) -> list[MachineHandle]:
        return list(self._handles.values())

    def __len__(self) -> int:
        return len(self._handles)
