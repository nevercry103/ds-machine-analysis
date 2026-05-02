"""OPC-UA Protocol Adapter — Pilot implementation.

Supports Siemens S7-1500/1200, Codesys, Beckhoff TwinCAT.

The adapter has two modes:

1.  **Real mode** (`config.simulator = False`) — connects to an OPC-UA
    server with `asyncua`, polls the `CycleReady` flag, reads the
    `DB_CycleLog` data block, parses it into a `CycleLog`, publishes
    `cycle_complete` to the Data Bus, then sets `CycleReset` to ack.

2.  **Simulator mode** (`config.simulator = True`) — generates synthetic
    cycles directly without any PLC. Lets engineers run the full stack
    end-to-end on a laptop with no hardware. Cycle period is taken from
    `config.simulator_cycle_ms` with `simulator_jitter_ms` noise.

Both modes publish identical events to the bus, so the rest of the
platform (cycle processor, storage, API, PWA) is mode-agnostic.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from core.data_bus import MachineDataBus
from core.data_model import (
    CycleLog,
    CycleStatus,
    DataBusEvent,
    MachineConfig,
    MachineStatus,
    StepLog,
    StepStatus,
)
from utils.logger import log

from .base_adapter import BaseProtocolAdapter


class OpcUaAdapter(BaseProtocolAdapter):
    """OPC-UA adapter (Siemens S7-1500 pilot via asyncua) + simulator mode."""

    POLL_INTERVAL_S = 0.1  # 100 ms — matches DataBus expectations
    RECONNECT_BACKOFF_S = 5.0

    def __init__(self, config: MachineConfig, bus: MachineDataBus) -> None:
        super().__init__(config, bus)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._client = None  # asyncua.Client when in real mode
        self._cycle_counter = 0

    async def start(self, *, initial_cycle_id: int = 0) -> None:
        if self._task is not None:
            return
        # Seed the counter so we resume from `initial_cycle_id + 1` on the
        # very next cycle. In real-PLC mode the PLC owns the counter so
        # this is a fallback; in simulator mode this is the mechanism
        # that prevents UNIQUE(cycle_id) collisions on restart.
        self._cycle_counter = max(self._cycle_counter, initial_cycle_id)
        self._stop.clear()
        if self.config.protocol.simulator:
            self._task = asyncio.create_task(
                self._run_simulator(), name=f"opcua-sim-{self.machine_id}"
            )
        else:
            self._task = asyncio.create_task(
                self._run_real(), name=f"opcua-{self.machine_id}"
            )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._set_status(MachineStatus.OFFLINE)

    # ---- simulator ----------------------------------------------------------

    async def _run_simulator(self) -> None:
        proto = self.config.protocol
        log.info(
            "OPC-UA adapter running in SIMULATOR mode",
            machine_id=self.machine_id,
            cycle_ms=proto.simulator_cycle_ms,
            jitter_ms=proto.simulator_jitter_ms,
        )
        self._set_status(MachineStatus.IDLE)

        period_s = proto.simulator_cycle_ms / 1000.0
        jitter_s = proto.simulator_jitter_ms / 1000.0

        while not self._stop.is_set():
            try:
                self._set_status(MachineStatus.BUSY)
                cycle = self._build_simulated_cycle()
                await self._publish_cycle(cycle)
                self._set_status(MachineStatus.IDLE)
                # Wait the simulator period (with jitter) before next cycle
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=max(0.05, period_s + random.uniform(-jitter_s, jitter_s)),
                )
            except asyncio.TimeoutError:
                continue  # normal — next tick
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.exception(
                    "Simulator iteration failed",
                    machine_id=self.machine_id,
                    error=str(exc),
                )
                self._set_status(MachineStatus.FAULT)
                await asyncio.sleep(self.RECONNECT_BACKOFF_S)

    def _build_simulated_cycle(self) -> CycleLog:
        """Generate a synthetic cycle whose step times jitter around a baseline.

        Baselines are deliberately non-uniform so one step is the bottleneck.
        Jitter is ~5% of the baseline, with rare 2x outliers to exercise
        Cycle Variance / outlier detection.

        When `replay_enabled`, every step also carries a `tag_values`
        dict — one entry per `replay_tags` declared in the YAML — so
        Replay Mode (F-005) can render the full machine state at each
        step boundary in the past.
        """
        self._cycle_counter += 1
        now = datetime.now(timezone.utc)

        n_steps = max(1, self.config.total_steps)
        baselines_ms = [300.0 + 200.0 * (k + 1) for k in range(n_steps)]

        steps: list[StepLog] = []
        cursor = now
        for k, baseline in enumerate(baselines_ms):
            jitter = baseline * 0.05 * random.gauss(0.0, 1.0)
            outlier = baseline if random.random() < 0.02 else 0.0
            duration_ms = max(50.0, baseline + jitter + outlier)
            t_end = cursor + timedelta(milliseconds=duration_ms)

            name = (
                self.config.step_names[k]
                if k < len(self.config.step_names)
                else f"Step {k + 1}"
            )

            steps.append(
                StepLog(
                    step_index=k + 1,
                    step_name=name,
                    timestamp_start=cursor,
                    timestamp_end=t_end,
                    duration_ms=duration_ms,
                    status=StepStatus.COMPLETED,
                    tag_values=self._simulate_tag_values(k + 1)
                    if self.config.replay_enabled
                    else {},
                )
            )
            cursor = t_end

        cycle = CycleLog(
            cycle_id=self._cycle_counter,
            machine_id=self.machine_id,
            timestamp_start=now,
            timestamp_end=cursor,
            steps=steps,
            total_duration_ms=sum(s.duration_ms for s in steps),
            status=CycleStatus.COMPLETED,
        )
        return cycle

    def _simulate_tag_values(self, step_index: int) -> dict:
        """Generate plausible synthetic values for the configured replay tags.

        Distributions are chosen by `kind`:
            number  -> drift around a tag-specific seeded baseline
            bool    -> 90% TRUE / 10% FALSE
            string  -> rotating pseudo-status string

        The seed is hash(tag_name) so the same tag has consistent
        baseline across cycles — engineers reviewing replays see a
        stable signal to compare against.
        """
        out: dict[str, float | int | bool | str] = {}
        for tag in self.config.replay_tags:
            seed = abs(hash(tag.name)) % 1000
            if tag.kind == "bool":
                out[tag.name] = random.random() < 0.9
            elif tag.kind == "string":
                states = ["RUN", "WAIT", "BLOCK", "READY"]
                out[tag.name] = states[(seed + step_index) % len(states)]
            else:
                # number — drift around a per-tag baseline
                baseline = 50.0 + (seed % 200)
                noise = random.gauss(0.0, baseline * 0.03)
                out[tag.name] = round(baseline + noise, 2)
        return out

    # ---- real mode ----------------------------------------------------------

    async def _run_real(self) -> None:
        # Lazy import so simulator mode works even if asyncua is missing.
        try:
            from asyncua import Client  # type: ignore
        except ImportError as exc:  # pragma: no cover
            log.error(
                "asyncua not installed; cannot run OPC-UA in real mode",
                machine_id=self.machine_id,
                error=str(exc),
            )
            self._set_status(MachineStatus.FAULT)
            return

        while not self._stop.is_set():
            try:
                self._set_status(MachineStatus.CONNECTING)
                self._client = Client(url=self.config.protocol.url)
                await self._client.connect()
                self._set_status(MachineStatus.IDLE)
                log.info(
                    "OPC-UA connected", machine_id=self.machine_id, url=self.config.protocol.url
                )
                await self._poll_loop()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning(
                    "OPC-UA connect/poll failed; backing off",
                    machine_id=self.machine_id,
                    error=str(exc),
                )
                self._set_status(MachineStatus.FAULT)
                if self._client is not None:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass
                    self._client = None
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.RECONNECT_BACKOFF_S
                    )
                    break  # stop signalled
                except asyncio.TimeoutError:
                    continue

    async def _poll_loop(self) -> None:
        """Poll CycleReady flag — when TRUE, read CycleLog, publish, ack.

        TODO Phase 1.x: the CycleLog node layout below is the canonical
        UDT defined in `plc_templates/siemens_s7/FB_CycleMaster.scl`.
        Hooking this up against real hardware is the next milestone.
        """
        if self._client is None:
            return

        proto = self.config.protocol
        ready_node = self._client.get_node(
            f"ns={proto.namespace};s={proto.cycle_ready_tag}"
        )
        reset_node = self._client.get_node(
            f"ns={proto.namespace};s={proto.cycle_reset_tag}"
        )
        log_node = self._client.get_node(
            f"ns={proto.namespace};s={proto.cycle_log_tag}"
        )

        while not self._stop.is_set():
            try:
                ready = await ready_node.read_value()
                if ready:
                    self._set_status(MachineStatus.BUSY)
                    cycle = await self._read_cycle_log(log_node)
                    if cycle is not None:
                        await self._publish_cycle(cycle)
                    await reset_node.write_value(True)
                    # Wait until PLC clears CycleReady
                    while await ready_node.read_value() and not self._stop.is_set():
                        await asyncio.sleep(self.POLL_INTERVAL_S)
                    await reset_node.write_value(False)
                    self._set_status(MachineStatus.IDLE)
                else:
                    await asyncio.sleep(self.POLL_INTERVAL_S)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Bubble up to reconnect logic
                raise

    async def _read_cycle_log(self, log_node) -> CycleLog | None:
        """Translate PLC UDT_CycleLog into the platform `CycleLog`.

        The exact field layout depends on the SCL template. Phase 1.x
        deliverable: implement this against the pilot S7-1500 firmware.
        For now, real mode is not invoked in the smoke test (only
        simulator mode runs end-to-end).
        """
        log.warning(
            "Real-mode CycleLog parser not yet wired to PLC UDT",
            machine_id=self.machine_id,
        )
        return None

    # ---- common -------------------------------------------------------------

    async def _publish_cycle(self, cycle: CycleLog) -> None:
        await self.bus.publish(
            DataBusEvent(
                machine_id=self.machine_id,
                event_type="cycle_complete",
                timestamp=cycle.timestamp_end,
                payload={"cycle_log": cycle},
            )
        )
