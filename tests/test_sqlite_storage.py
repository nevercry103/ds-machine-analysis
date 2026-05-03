"""Integration-style tests for the SQLite storage backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from core.data_model import CycleLog, CycleStatus, StepLog, StepStatus
from storage.sqlite_storage import SqliteStorage


def _cycle(cycle_id: int, machine_id: str = "machine_001") -> CycleLog:
    start = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(milliseconds=100)
    return CycleLog(
        cycle_id=cycle_id,
        machine_id=machine_id,
        timestamp_start=start,
        timestamp_end=end,
        steps=[
            StepLog(
                step_index=1,
                step_name="Loading",
                timestamp_start=start,
                timestamp_end=end,
                duration_ms=100.0,
                status=StepStatus.COMPLETED,
            )
        ],
        total_duration_ms=100.0,
        status=CycleStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_sqlite_storage_connect_and_save_cycle():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "test_storage.db")
        assert await storage.connect() is True

        assert await storage.save_cycle(_cycle(1)) is True

        loaded = await storage.get_cycle("machine_001", 1)
        assert loaded is not None
        assert loaded.machine_id == "machine_001"
        assert loaded.cycle_id == 1
        assert len(loaded.steps) == 1
        assert loaded.steps[0].step_name == "Loading"

        recent = await storage.get_cycles("machine_001", limit=10)
        assert len(recent) == 1

        await storage.disconnect()


@pytest.mark.asyncio
async def test_get_last_cycle_id_empty_returns_zero():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "empty.db")
        await storage.connect()

        assert await storage.get_last_cycle_id("machine_001") == 0

        await storage.disconnect()


@pytest.mark.asyncio
async def test_get_last_cycle_id_returns_max():
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "max.db")
        await storage.connect()

        for cid in (1, 2, 3, 5, 4):  # not in order
            assert await storage.save_cycle(_cycle(cid)) is True

        assert await storage.get_last_cycle_id("machine_001") == 5
        # Different machine isolated
        assert await storage.get_last_cycle_id("other") == 0

        await storage.disconnect()


@pytest.mark.asyncio
async def test_duplicate_cycle_id_is_silently_skipped():
    """The whole point of the F-002 fix: restart against existing DB
    must not raise UNIQUE-constraint errors. Duplicate save returns
    False but does not throw, and the original row is preserved.
    """
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "dup.db")
        await storage.connect()

        assert await storage.save_cycle(_cycle(1)) is True
        # Same cycle_id again — must not raise.
        assert await storage.save_cycle(_cycle(1)) is False

        # Original row + steps survive untouched.
        loaded = await storage.get_cycle("machine_001", 1)
        assert loaded is not None
        assert len(loaded.steps) == 1

        # Only one row total.
        recent = await storage.get_cycles("machine_001", limit=10)
        assert len(recent) == 1

        await storage.disconnect()


@pytest.mark.asyncio
async def test_delete_old_data_removes_expired_cycles():
    """Retention cleanup deletes cycles older than cutoff."""
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "retention.db")
        await storage.connect()

        # Old cycle: 30 days ago
        old = _cycle(1)
        old.timestamp_start = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
        old.timestamp_end = datetime(2026, 4, 1, 10, 0, 1, tzinfo=timezone.utc)
        assert await storage.save_cycle(old) is True

        # Recent cycle: now
        recent_cycle = _cycle(2)
        recent_cycle.timestamp_start = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
        recent_cycle.timestamp_end = datetime(2026, 5, 2, 10, 0, 1, tzinfo=timezone.utc)
        assert await storage.save_cycle(recent_cycle) is True

        # Delete anything before May 1
        cutoff = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        deleted = await storage.delete_old_data(cutoff)
        assert deleted >= 1

        # Old cycle gone, recent survives
        assert await storage.get_cycle("machine_001", 1) is None
        assert await storage.get_cycle("machine_001", 2) is not None

        await storage.disconnect()


@pytest.mark.asyncio
async def test_delete_old_data_scoped_to_machine():
    """Retention cleanup with machine_id only affects that machine."""
    with TemporaryDirectory() as tmpdir:
        storage = SqliteStorage(Path(tmpdir) / "scope.db")
        await storage.connect()

        old_ts_start = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
        old_ts_end = datetime(2026, 4, 1, 10, 0, 1, tzinfo=timezone.utc)

        c1 = _cycle(1, machine_id="m1")
        c1.timestamp_start = old_ts_start
        c1.timestamp_end = old_ts_end
        await storage.save_cycle(c1)

        c2 = _cycle(1, machine_id="m2")
        c2.timestamp_start = old_ts_start
        c2.timestamp_end = old_ts_end
        await storage.save_cycle(c2)

        cutoff = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        await storage.delete_old_data(cutoff, machine_id="m1")

        # m1 cycle deleted, m2 cycle intact
        assert await storage.get_cycle("m1", 1) is None
        assert await storage.get_cycle("m2", 1) is not None

        await storage.disconnect()
