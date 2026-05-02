"""Replay Mode tests — tag_values round-trip through storage + adapter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from core.data_model import (
    CycleLog,
    CycleStatus,
    MachineConfig,
    ProtocolConfig,
    ReplayTagDef,
    StepLog,
    StepStatus,
)
from core.data_bus import MachineDataBus
from plc.opcua_adapter import OpcUaAdapter
from storage.sqlite_storage import SqliteStorage


def _cycle_with_tags(cycle_id: int) -> CycleLog:
    start = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(milliseconds=300)
    return CycleLog(
        cycle_id=cycle_id,
        machine_id="m1",
        timestamp_start=start,
        timestamp_end=end,
        steps=[
            StepLog(
                step_index=1,
                step_name="Pick",
                timestamp_start=start,
                timestamp_end=end,
                duration_ms=300.0,
                status=StepStatus.COMPLETED,
                tag_values={
                    "spindle_rpm": 1234.5,
                    "vacuum_ok": True,
                    "robot_state": "RUN",
                },
            )
        ],
        total_duration_ms=300.0,
        status=CycleStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_tag_values_round_trip_through_sqlite():
    """save_cycle -> get_cycle preserves the tag_values dict verbatim."""
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "replay.db")
        await storage.connect()

        await storage.save_cycle(_cycle_with_tags(7))
        loaded = await storage.get_cycle("m1", 7)

        assert loaded is not None
        assert len(loaded.steps) == 1
        assert loaded.steps[0].tag_values == {
            "spindle_rpm": 1234.5,
            "vacuum_ok": True,
            "robot_state": "RUN",
        }
        await storage.disconnect()


@pytest.mark.asyncio
async def test_simulator_emits_tag_values_when_replay_enabled():
    """When replay_enabled=True the simulator must populate tag_values
    on every step. When False, tag_values stays empty.
    """
    bus = MachineDataBus("m_sim")

    config_replay = MachineConfig(
        machine_id="m_sim",
        machine_name="Sim",
        protocols=[ProtocolConfig(type="opcua", url="opc.tcp://localhost:4840", namespace=3, simulator=True)],
        total_steps=2,
        step_names=["A", "B"],
        replay_enabled=True,
        replay_tags=[
            ReplayTagDef(name="rpm", address="x", kind="number"),
            ReplayTagDef(name="ok", address="y", kind="bool"),
            ReplayTagDef(name="state", address="z", kind="string"),
        ],
    )
    adapter = OpcUaAdapter(config_replay, bus)
    cycle = adapter._build_simulated_cycle()
    assert all(set(s.tag_values.keys()) == {"rpm", "ok", "state"} for s in cycle.steps)
    # Types preserved
    rpm = cycle.steps[0].tag_values["rpm"]
    assert isinstance(rpm, (int, float))
    assert isinstance(cycle.steps[0].tag_values["ok"], bool)
    assert isinstance(cycle.steps[0].tag_values["state"], str)

    config_no_replay = MachineConfig(
        machine_id="m_sim2",
        machine_name="Sim2",
        protocols=[ProtocolConfig(type="opcua", url="opc.tcp://localhost:4840", namespace=3, simulator=True)],
        total_steps=2,
        step_names=["A", "B"],
        replay_enabled=False,
    )
    adapter2 = OpcUaAdapter(config_no_replay, MachineDataBus("m_sim2"))
    cycle2 = adapter2._build_simulated_cycle()
    assert all(s.tag_values == {} for s in cycle2.steps)


@pytest.mark.asyncio
async def test_sample_yaml_with_replay_loads_clean():
    """The replay-demo sample YAML must validate via MachineConfigSchema."""
    from core.config_model import MachineConfigSchema

    schema = MachineConfigSchema.from_yaml(
        Path("config/machines/machine_replay_demo.yaml.sample")
    )
    config = schema.to_machine_config()
    assert config.replay_enabled is True
    assert len(config.replay_tags) == 5
    assert {t.name for t in config.replay_tags} == {
        "spindle_rpm",
        "temperature_C",
        "pressure_bar",
        "vacuum_ok",
        "robot_state",
    }
    assert config.tier_required == "tier_5"
