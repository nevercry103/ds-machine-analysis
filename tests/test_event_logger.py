"""Event Logger tests — Pillar 3 (alarm + anomaly + downtime)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from core.data_bus import MachineDataBus
from core.data_model import (
    DataBusEvent,
    EventCategory,
    EventSeverity,
)
from core.event_logger import EventLogger, is_known_downtime_reason
from storage.sqlite_storage import SqliteStorage


@pytest.mark.asyncio
async def test_logger_persists_anomaly():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "events.db")
        await storage.connect()
        bus = MachineDataBus("m1")
        logger_ = EventLogger("m1", bus=bus, storage=storage)
        await logger_.start()

        await bus.publish(
            DataBusEvent(
                machine_id="m1",
                event_type="cycle_anomaly",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "step_index": 3,
                    "step_name": "Assembly",
                    "cv_pct": 12.5,
                    "threshold_pct": 8.0,
                },
            )
        )

        for _ in range(40):
            rows = await storage.get_events("m1", limit=10)
            if rows:
                break
            await asyncio.sleep(0.02)

        rows = await storage.get_events("m1", limit=10)
        assert len(rows) == 1
        assert rows[0].category == EventCategory.ANOMALY
        assert rows[0].severity == EventSeverity.WARNING
        assert rows[0].code == "VARIANCE_HIGH"
        assert "Assembly" in rows[0].message
        await bus.shutdown()
        await storage.disconnect()


@pytest.mark.asyncio
async def test_logger_persists_downtime():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "events2.db")
        await storage.connect()
        bus = MachineDataBus("m1")
        logger_ = EventLogger("m1", bus=bus, storage=storage)
        await logger_.start()

        await bus.publish(
            DataBusEvent(
                machine_id="m1",
                event_type="downtime_tag",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "reason": "material_out",
                    "note": "ran out of caps",
                    "by": "operator_42",
                },
            )
        )

        for _ in range(40):
            rows = await storage.get_events("m1", limit=10, category="downtime")
            if rows:
                break
            await asyncio.sleep(0.02)

        rows = await storage.get_events("m1", limit=10, category="downtime")
        assert len(rows) == 1
        assert rows[0].category == EventCategory.DOWNTIME
        assert rows[0].code == "DOWNTIME_MATERIAL_OUT"
        assert "operator_42" in rows[0].message
        assert rows[0].payload["reason"] == "material_out"
        await bus.shutdown()
        await storage.disconnect()


@pytest.mark.asyncio
async def test_logger_escalates_fault_status_to_warning():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "events3.db")
        await storage.connect()
        bus = MachineDataBus("m1")
        logger_ = EventLogger("m1", bus=bus, storage=storage)
        await logger_.start()

        await bus.publish(
            DataBusEvent(
                machine_id="m1",
                event_type="status_change",
                timestamp=datetime.now(timezone.utc),
                payload={"old": "idle", "status": "fault"},
            )
        )

        for _ in range(40):
            rows = await storage.get_events("m1", limit=10)
            if rows:
                break
            await asyncio.sleep(0.02)

        rows = await storage.get_events("m1", limit=10)
        assert len(rows) == 1
        assert rows[0].severity == EventSeverity.WARNING
        assert rows[0].category == EventCategory.STATUS
        await bus.shutdown()
        await storage.disconnect()


@pytest.mark.asyncio
async def test_logger_ignores_unrelated_event_types():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "events4.db")
        await storage.connect()
        bus = MachineDataBus("m1")
        logger_ = EventLogger("m1", bus=bus, storage=storage)
        await logger_.start()

        # cycle_summary is consumed by the API fan-out, NOT by EventLogger.
        await bus.publish(
            DataBusEvent(
                machine_id="m1",
                event_type="cycle_summary",
                timestamp=datetime.now(timezone.utc),
                payload={},
            )
        )
        await asyncio.sleep(0.1)

        rows = await storage.get_events("m1", limit=10)
        assert rows == []
        await bus.shutdown()
        await storage.disconnect()


@pytest.mark.asyncio
async def test_acknowledge_event_round_trip():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "events5.db")
        await storage.connect()
        bus = MachineDataBus("m1")
        logger_ = EventLogger("m1", bus=bus, storage=storage)
        await logger_.start()

        await bus.publish(
            DataBusEvent(
                machine_id="m1",
                event_type="alarm",
                timestamp=datetime.now(timezone.utc),
                payload={"code": "EMG_STOP", "message": "E-stop pressed"},
            )
        )

        for _ in range(40):
            rows = await storage.get_events("m1")
            if rows:
                break
            await asyncio.sleep(0.02)

        rows = await storage.get_events("m1")
        assert rows[0].acknowledged is False

        updated = await storage.acknowledge_event(
            rows[0].id, acknowledged_by="ha"
        )
        assert updated is not None
        assert updated.acknowledged is True
        assert updated.acknowledged_by == "ha"
        assert updated.acknowledged_at is not None
        await bus.shutdown()
        await storage.disconnect()


def test_known_downtime_reasons_validation():
    assert is_known_downtime_reason("material_out")
    assert is_known_downtime_reason("Material_Out")  # case-insensitive
    assert is_known_downtime_reason(" unknown ")
    assert not is_known_downtime_reason("not_a_reason")
    assert not is_known_downtime_reason("")
