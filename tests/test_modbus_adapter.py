"""Modbus adapter tests — simulator mode (no real PLC)."""

from __future__ import annotations

import asyncio

import pytest

from core.data_bus import MachineDataBus
from core.data_model import MachineConfig, ProtocolConfig
from plc.modbus_adapter import ModbusAdapter


def _modbus_config() -> MachineConfig:
    return MachineConfig(
        machine_id="modbus_test",
        machine_name="Modbus Test Machine",
        protocols=[
            ProtocolConfig(
                type="modbus_tcp",
                url="modbus://localhost:502",
                simulator=True,
                simulator_cycle_ms=200,
                simulator_jitter_ms=20,
            )
        ],
        total_steps=3,
        step_names=["Load", "Process", "Unload"],
    )


@pytest.mark.asyncio
async def test_modbus_simulator_produces_cycles():
    """Simulator mode generates cycles published to the bus."""
    config = _modbus_config()
    bus = MachineDataBus(config.machine_id)
    adapter = ModbusAdapter(config, bus)

    received: list[dict] = []

    async def collector(event):
        if event.event_type == "cycle_complete":
            received.append(event.payload)

    await bus.subscribe("test_collector", collector)
    await adapter.start(initial_cycle_id=0)

    # Wait for at least 2 cycles (~0.4s)
    await asyncio.sleep(1.0)
    await adapter.stop()

    assert len(received) >= 2
    cycle = received[0]["cycle_log"]
    assert cycle.machine_id == "modbus_test"
    assert len(cycle.steps) == 3
    assert cycle.steps[0].step_name == "Load"


@pytest.mark.asyncio
async def test_modbus_resumes_cycle_counter():
    """initial_cycle_id seeds the counter so IDs don't restart at 1."""
    config = _modbus_config()
    bus = MachineDataBus(config.machine_id)
    adapter = ModbusAdapter(config, bus)

    received = []

    async def collector(event):
        if event.event_type == "cycle_complete":
            received.append(event.payload["cycle_log"].cycle_id)

    await bus.subscribe("test", collector)
    await adapter.start(initial_cycle_id=100)
    await asyncio.sleep(0.5)
    await adapter.stop()

    assert received
    assert received[0] == 101  # resumes from 100 + 1


@pytest.mark.asyncio
async def test_modbus_factory_builds_adapter():
    """build_adapter returns a ModbusAdapter for modbus_tcp type."""
    from plc import build_adapter

    config = _modbus_config()
    bus = MachineDataBus(config.machine_id)
    adapter = build_adapter(config, bus)
    assert isinstance(adapter, ModbusAdapter)
