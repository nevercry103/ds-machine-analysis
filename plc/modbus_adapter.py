"""Modbus TCP Protocol Adapter — Phase 4.

Supports Modbus TCP devices (Schneider, Delta, Panasonic, generic PLCs).

Like the OPC-UA adapter, operates in two modes:
1. **Real mode** — connects to a Modbus TCP server via `pymodbus`,
   polls holding registers for the CycleReady flag, reads cycle data
   registers, publishes to the Data Bus, then writes CycleReset.
2. **Simulator mode** — generates synthetic cycles without hardware.

Register layout (configurable via YAML):
  - CycleReady:  holding register (default 100), value 1 = ready
  - CycleReset:  holding register (default 101), write 1 to ack
  - CycleLog:    contiguous block of holding registers starting at
                 `cycle_log_tag` (default 200), containing:
                   [cycle_id_hi, cycle_id_lo, step_count,
                    step_1_ms_hi, step_1_ms_lo, ...,
                    step_N_ms_hi, step_N_ms_lo]

Architecture layer: PROTOCOL LAYER
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


class ModbusAdapter(BaseProtocolAdapter):
    """Modbus TCP adapter with real + simulator modes."""

    POLL_INTERVAL_S = 0.2  # 200 ms — Modbus is slower than OPC-UA
    RECONNECT_BACKOFF_S = 5.0

    def __init__(self, config: MachineConfig, bus: MachineDataBus) -> None:
        super().__init__(config, bus)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._client = None
        self._cycle_counter = 0

    async def start(self, *, initial_cycle_id: int = 0) -> None:
        if self._task is not None:
            return
        self._cycle_counter = max(self._cycle_counter, initial_cycle_id)
        self._stop.clear()
        if self.config.protocol.simulator:
            self._task = asyncio.create_task(
                self._run_simulator(), name=f"modbus-sim-{self.machine_id}"
            )
        else:
            self._task = asyncio.create_task(
                self._run_real(), name=f"modbus-{self.machine_id}"
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
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._set_status(MachineStatus.OFFLINE)

    # ---- Real mode -------------------------------------------------------

    async def _run_real(self) -> None:
        """Connect to Modbus TCP server and poll for cycles."""
        self._set_status(MachineStatus.CONNECTING)

        while not self._stop.is_set():
            try:
                client = await self._connect()
                self._client = client
                self._set_status(MachineStatus.IDLE)

                while not self._stop.is_set():
                    ready = await self._read_cycle_ready()
                    if ready:
                        self._set_status(MachineStatus.BUSY)
                        cycle = await self._read_cycle_log()
                        if cycle is not None:
                            await self.bus.publish(
                                DataBusEvent(
                                    machine_id=self.machine_id,
                                    event_type="cycle_complete",
                                    timestamp=cycle.timestamp_end,
                                    payload={"cycle_log": cycle},
                                )
                            )
                            await self._write_cycle_reset()
                        self._set_status(MachineStatus.IDLE)
                    await asyncio.sleep(self.POLL_INTERVAL_S)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning(
                    "Modbus connection lost, reconnecting",
                    machine_id=self.machine_id,
                    error=str(exc),
                )
                self._set_status(MachineStatus.CONNECTING)
                await asyncio.sleep(self.RECONNECT_BACKOFF_S)

    async def _connect(self):
        """Connect to the Modbus TCP server using pymodbus."""
        from pymodbus.client import AsyncModbusTcpClient

        # Parse URL — expected format: "modbus://host:port" or "host:port"
        url = self.config.protocol.url
        url = url.replace("modbus://", "")
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            port = int(port_str)
        else:
            host = url
            port = 502

        client = AsyncModbusTcpClient(host, port=port)
        connected = await client.connect()
        if not connected:
            raise ConnectionError(f"Cannot connect to Modbus TCP {host}:{port}")
        log.info("Modbus TCP connected", host=host, port=port)
        return client

    async def _read_cycle_ready(self) -> bool:
        """Read the CycleReady holding register."""
        addr = int(self.config.protocol.cycle_ready_tag)
        result = await self._client.read_holding_registers(addr, count=1)
        if result.isError():
            return False
        return result.registers[0] == 1

    async def _read_cycle_log(self) -> CycleLog | None:
        """Read cycle data from contiguous holding registers."""
        base_addr = int(self.config.protocol.cycle_log_tag)
        total_steps = self.config.total_steps
        # Layout: [cycle_id(2), step_count(1), step_ms(2*N)]
        reg_count = 3 + (total_steps * 2)

        result = await self._client.read_holding_registers(base_addr, count=reg_count)
        if result.isError():
            log.warning("Modbus read cycle_log failed", machine_id=self.machine_id)
            return None

        regs = result.registers
        cycle_id = (regs[0] << 16) | regs[1]
        step_count = regs[2]

        now = datetime.now(timezone.utc)
        steps: list[StepLog] = []
        cursor = now

        for i in range(min(step_count, total_steps)):
            ms_hi = regs[3 + i * 2]
            ms_lo = regs[4 + i * 2]
            duration_ms = float((ms_hi << 16) | ms_lo)
            step_start = cursor
            step_end = cursor + timedelta(milliseconds=duration_ms)
            steps.append(
                StepLog(
                    step_index=i + 1,
                    step_name=self.config.step_names[i] if i < len(self.config.step_names) else f"Step {i+1}",
                    timestamp_start=step_start,
                    timestamp_end=step_end,
                    duration_ms=duration_ms,
                    status=StepStatus.COMPLETED,
                )
            )
            cursor = step_end

        total_ms = sum(s.duration_ms for s in steps)
        return CycleLog(
            cycle_id=cycle_id,
            machine_id=self.machine_id,
            timestamp_start=steps[0].timestamp_start if steps else now,
            timestamp_end=steps[-1].timestamp_end if steps else now,
            steps=steps,
            total_duration_ms=total_ms,
            status=CycleStatus.COMPLETED,
        )

    async def _write_cycle_reset(self) -> None:
        """Write 1 to the CycleReset register to acknowledge."""
        addr = int(self.config.protocol.cycle_reset_tag)
        await self._client.write_register(addr, 1)
        # Wait briefly, then clear
        await asyncio.sleep(0.1)
        await self._client.write_register(addr, 0)

    # ---- Simulator mode --------------------------------------------------

    async def _run_simulator(self) -> None:
        """Generate synthetic cycles — same logic as OpcUaAdapter simulator."""
        self._set_status(MachineStatus.IDLE)
        proto = self.config.protocol
        cycle_ms = proto.simulator_cycle_ms
        jitter_ms = proto.simulator_jitter_ms
        total_steps = self.config.total_steps

        while not self._stop.is_set():
            actual_ms = cycle_ms + random.randint(-jitter_ms, jitter_ms)
            per_step_ms = actual_ms / max(total_steps, 1)

            self._set_status(MachineStatus.BUSY)
            await asyncio.sleep(actual_ms / 1000.0)

            self._cycle_counter += 1
            now = datetime.now(timezone.utc)
            start = now - timedelta(milliseconds=actual_ms)
            steps: list[StepLog] = []
            cursor = start

            for i in range(total_steps):
                step_dur = per_step_ms + random.uniform(
                    -per_step_ms * 0.15, per_step_ms * 0.15
                )
                step_dur = max(1.0, step_dur)
                step_end = cursor + timedelta(milliseconds=step_dur)
                steps.append(
                    StepLog(
                        step_index=i + 1,
                        step_name=(
                            self.config.step_names[i]
                            if i < len(self.config.step_names)
                            else f"Step {i + 1}"
                        ),
                        timestamp_start=cursor,
                        timestamp_end=step_end,
                        duration_ms=step_dur,
                        status=StepStatus.COMPLETED,
                        tag_values={},
                    )
                )
                cursor = step_end

            cycle = CycleLog(
                cycle_id=self._cycle_counter,
                machine_id=self.machine_id,
                timestamp_start=start,
                timestamp_end=cursor,
                steps=steps,
                total_duration_ms=sum(s.duration_ms for s in steps),
                status=CycleStatus.COMPLETED,
            )

            await self.bus.publish(
                DataBusEvent(
                    machine_id=self.machine_id,
                    event_type="cycle_complete",
                    timestamp=cycle.timestamp_end,
                    payload={"cycle_log": cycle},
                )
            )
            self._set_status(MachineStatus.IDLE)
