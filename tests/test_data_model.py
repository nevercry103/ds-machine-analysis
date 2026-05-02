"""
tests/test_data_model.py

Unit tests for core data models.
"""

import pytest
from datetime import datetime
from core.data_model import StepLog, CycleLog, StepStatus, CycleStatus


def test_step_log_creation():
    """Test StepLog creation."""
    now = datetime.utcnow()
    step = StepLog(
        step_index=1,
        step_name="Loading",
        timestamp_start=now,
        timestamp_end=datetime.fromtimestamp(now.timestamp() + 0.1),  # +100ms
        duration_ms=100.0
    )
    assert step.step_index == 1
    assert step.duration_ms == 100.0
    assert step.status == StepStatus.COMPLETED


def test_cycle_log_creation():
    """Test CycleLog basic creation."""
    cycle = CycleLog(
        cycle_id=1,
        machine_id="machine_001",
        timestamp_start=datetime.utcnow(),
        timestamp_end=datetime.utcnow()
    )
    assert cycle.cycle_id == 1
    assert cycle.machine_id == "machine_001"
    assert cycle.status == CycleStatus.IDLE


def test_cycle_log_add_step():
    """Test adding steps to cycle."""
    now = datetime.utcnow()
    cycle = CycleLog(
        cycle_id=1,
        machine_id="machine_001",
        timestamp_start=now,
        timestamp_end=now
    )

    step = StepLog(
        step_index=1,
        step_name="Loading",
        timestamp_start=now,
        timestamp_end=datetime.fromtimestamp(now.timestamp() + 0.1),
        duration_ms=100.0
    )
    cycle.add_step(step)
    assert len(cycle.steps) == 1
    assert cycle.total_duration_ms == 100.0


def test_step_log_invalid_duration():
    """Test that invalid step duration raises error."""
    now = datetime.utcnow()
    with pytest.raises(ValueError):
        StepLog(
            step_index=1,
            step_name="Invalid",
            timestamp_start=now,
            timestamp_end=datetime.fromtimestamp(now.timestamp() - 1),  # end < start
            duration_ms=-1000.0
        )
