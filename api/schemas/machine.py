"""Machine + Cycle wire schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MachineSummary(BaseModel):
    """High-level machine status — used for list views and cards."""

    id: str
    name: str
    enabled: bool
    status: Literal["online", "offline", "fault", "idle", "busy", "connecting"] = "offline"
    protocol_type: str = Field(description="opcua | modbus_tcp | ethernet_ip | ...")
    current_cycle_step: int | None = None
    last_cycle_ms: int | None = None
    last_cycle_id: int | None = None
    cycle_count: int = 0


class StepSummary(BaseModel):
    index: int
    name: str
    duration_ms: int
    started_at: datetime
    ended_at: datetime


class CycleSummary(BaseModel):
    """One completed cycle — what the UI/PWA renders in Gantt + history table."""

    machine_id: str
    cycle_id: int
    started_at: datetime
    ended_at: datetime
    total_ms: int
    steps: list[StepSummary]
    bottleneck_step_index: int | None = None
    bottleneck_step_ms: int | None = None


class StepReplay(BaseModel):
    """One step from the Replay Mode response — includes tag values."""

    index: int
    name: str
    duration_ms: int
    started_at: datetime
    ended_at: datetime
    tag_values: dict[str, float | int | bool | str] = Field(default_factory=dict)


class CycleReplay(BaseModel):
    """Full replay payload — engineer scrubs through this in the UI.

    F-005: every step carries the snapshot of configured `replay_tags`,
    captured at the step boundary by the protocol adapter.
    """

    machine_id: str
    cycle_id: int
    started_at: datetime
    ended_at: datetime
    total_ms: int
    steps: list[StepReplay]
    replay_tag_count: int = 0


class OEEResponse(BaseModel):
    """Pillar 2 — current OEE snapshot for a machine."""

    machine_id: str
    window_start: datetime
    window_end: datetime
    window_minutes: int
    cycles_completed: int
    cycles_aborted: int
    run_time_ms: float
    planned_time_ms: float
    ideal_cycle_ms: float
    availability: float = Field(..., ge=0.0, le=1.0)
    performance: float = Field(..., ge=0.0, le=1.0)
    quality: float = Field(..., ge=0.0, le=1.0)
    oee: float = Field(..., ge=0.0, le=1.0)


class EventLogResponse(BaseModel):
    """Pillar 3 — one row from the event log."""

    id: int
    machine_id: str
    timestamp: datetime
    severity: str
    category: str
    code: str
    message: str
    payload: dict = Field(default_factory=dict)
    acknowledged: bool
    acknowledged_by: str
    acknowledged_at: datetime | None = None


class DowntimeRequest(BaseModel):
    """Operator-as-Sensor — POST body for tagging downtime."""

    reason: str = Field(..., min_length=1, max_length=64)
    note: str = Field("", max_length=500)
    by: str = Field("operator", max_length=128)


class EventAckRequest(BaseModel):
    acknowledged_by: str = Field(..., min_length=1, max_length=128)
