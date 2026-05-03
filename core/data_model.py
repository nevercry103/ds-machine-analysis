"""Data models for DS Machine Analyzer Platform.

Single source of truth for all dataclasses. No model definitions in
other modules. All timestamps from the PLC (ts_start / ts_end);
`created_at` is server wall-clock used only for retention/ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utc_now() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)


class StepStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class CycleStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"


class MachineStatus(str, Enum):
    """Lifecycle state exposed to API consumers."""

    OFFLINE = "offline"
    CONNECTING = "connecting"
    IDLE = "idle"
    BUSY = "busy"
    FAULT = "fault"


@dataclass
class StepLog:
    """One step in a cycle. Timestamps come from PLC, never Python.

    `tag_values` carries a snapshot of the configured replay tags taken
    at the step boundary (Replay Mode, F-005). Empty when the machine
    config does not declare `replay.tags`. Values are JSON-serializable
    primitives (number / bool / str) — complex PLC types must be coerced
    by the adapter before publishing.
    """

    step_index: int
    step_name: str
    timestamp_start: datetime
    timestamp_end: datetime
    duration_ms: float
    status: StepStatus = StepStatus.COMPLETED
    tag_values: dict[str, float | int | bool | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_end < self.timestamp_start:
            raise ValueError("Invalid step duration: end < start")


@dataclass
class CycleLog:
    """Complete cycle log — mirrors PLC UDT_CycleLog."""

    cycle_id: int
    machine_id: str
    timestamp_start: datetime
    timestamp_end: datetime
    steps: list[StepLog] = field(default_factory=list)
    total_duration_ms: float = 0.0
    status: CycleStatus = CycleStatus.IDLE
    created_at: datetime = field(default_factory=_utc_now)

    def add_step(self, step: StepLog) -> None:
        self.steps.append(step)
        self.total_duration_ms = sum(s.duration_ms for s in self.steps)

    def mark_completed(self) -> None:
        self.status = CycleStatus.COMPLETED


@dataclass
class ReplayTagDef:
    """One tag captured per step for Replay Mode (F-005).

    `name` is the local label rendered in the UI; `address` is the
    protocol-specific OPC-UA / Modbus / EtherNet-IP address (for the
    real adapter). `kind` is a hint for the simulator: number, bool,
    or string — drives the synthetic distribution.
    """

    name: str
    address: str
    kind: str = "number"  # number | bool | string
    unit: str = ""


@dataclass
class ShiftDef:
    """One shift in the factory schedule.

    `start_hour` and `end_hour` are 0-23 integers. Overnight shifts
    where start > end (e.g., 22:00-06:00) are supported.
    """

    name: str
    start_hour: int  # 0-23
    end_hour: int    # 0-23

    def contains(self, hour: int) -> bool:
        """Return True if `hour` (0-23) falls within this shift."""
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        # Overnight shift (e.g., 22-06)
        return hour >= self.start_hour or hour < self.end_hour


# Default shifts when none configured — single 24h shift.
DEFAULT_SHIFTS: tuple[ShiftDef, ...] = (
    ShiftDef(name="All day", start_hour=0, end_hour=0),
)


def resolve_shift(shifts: list[ShiftDef], hour: int) -> str:
    """Return the shift name for a given hour (0-23)."""
    if not shifts:
        return "All day"
    for s in shifts:
        if s.start_hour == s.end_hour:
            return s.name  # 24h catch-all
        if s.contains(hour):
            return s.name
    return "Unscheduled"


@dataclass
class ProtocolConfig:
    """Configuration for one physical PLC connection.

    A logical machine owns 1..N ProtocolConfigs (F-004: multi-PLC per
    machine). Phase 1 enforces N=1; Phase 4 lifts the restriction so a
    main PLC + safety PLC + drive PLC can share one logical machine.
    """

    type: str
    url: str
    namespace: int | None = None

    cycle_ready_tag: str = "CycleReady"
    cycle_reset_tag: str = "CycleReset"
    cycle_log_tag: str = "DB_CycleLog"

    # Simulator mode — when True, no real PLC connection is made; the
    # adapter generates synthetic cycles useful for headless dev/test.
    simulator: bool = False
    simulator_cycle_ms: int = 5000
    simulator_jitter_ms: int = 200


@dataclass
class MachineConfig:
    """Machine configuration loaded from YAML.

    1 file per machine (`config/machines/machine_XXX.yaml`).
    1 logical machine = N physical PLCs (F-004), unified clock.
    """

    machine_id: str
    machine_name: str

    # F-004: list of protocol connections. Phase 1 enforces len == 1.
    protocols: list[ProtocolConfig] = field(default_factory=list)

    total_steps: int = 1
    step_names: list[str] = field(default_factory=list)

    enabled: bool = True
    cycle_enabled: bool = True

    oee_enabled: bool = False
    oee_window_minutes: int = 60
    oee_ideal_cycle_ms: float = 0.0
    event_log_enabled: bool = False

    storage_mode: str = "sqlite"
    sqlite_path: str | None = None
    postgres_dsn: str | None = None

    # Replay Mode (F-005): configured PLC tags whose values are captured
    # at every step boundary. Empty list = Replay Mode off.
    replay_enabled: bool = False
    replay_tags: list[ReplayTagDef] = field(default_factory=list)

    # Multi-shift aggregation (Phase 2).
    shifts: list[ShiftDef] = field(default_factory=list)

    # Tier gating (F-006): refuse to load if license tier < required.
    tier_required: str = "tier_1"

    @property
    def protocol(self) -> ProtocolConfig:
        """Primary protocol — convenience accessor for Phase 1 (N=1).

        Phase 4 callers that support multi-PLC iterate `protocols` directly.
        """
        if not self.protocols:
            raise ValueError(f"Machine '{self.machine_id}' has no protocols configured")
        return self.protocols[0]


@dataclass
class DataBusEvent:
    """Normalized event posted to the per-machine data bus.

    Consumed by all pillars (Cycle / OEE / Event Log) and fanned out to
    API WebSocket subscribers.
    """

    machine_id: str
    event_type: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class OEESnapshot:
    """Pillar 2 — OEE = Availability x Performance x Quality.

    Computed over a rolling window (default 60 minutes). Values are
    ratios in the [0.0, 1.0] range; ``oee`` is always the product of
    the three component ratios.

    Definitions chosen to match SEMI E10 / typical SME shop-floor
    practice; deliberately simple for Phase 2 MVP:

      Availability = run_time_ms / planned_time_ms
                     where run_time_ms is the time the machine was in
                     BUSY or IDLE state during the window, and
                     planned_time_ms is the wall-clock window length
                     minus configured breaks (Phase 4).

      Performance  = (cycles_completed * ideal_cycle_ms) / run_time_ms
                     ratio of "ideal output" the machine produced.

      Quality      = cycles_completed / (cycles_completed + cycles_aborted)
                     1.0 when no aborts occurred. Phase 4 will add real
                     NG events from the PLC.
    """

    machine_id: str
    window_start: datetime
    window_end: datetime

    cycles_completed: int = 0
    cycles_aborted: int = 0
    run_time_ms: float = 0.0
    planned_time_ms: float = 0.0
    ideal_cycle_ms: float = 0.0

    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0
    oee: float = 0.0

    last_updated: datetime = field(default_factory=_utc_now)

    @classmethod
    def compute(
        cls,
        machine_id: str,
        *,
        window_start: datetime,
        window_end: datetime,
        cycles_completed: int,
        cycles_aborted: int,
        run_time_ms: float,
        ideal_cycle_ms: float,
    ) -> "OEESnapshot":
        planned_time_ms = max(
            0.0, (window_end - window_start).total_seconds() * 1000.0
        )

        # Clamp Availability — run_time can briefly exceed planned_time
        # if cycles span the window edge.
        availability = (
            min(1.0, run_time_ms / planned_time_ms) if planned_time_ms > 0 else 0.0
        )

        # Performance: ideal_cycle_ms must be > 0 and run_time_ms > 0.
        if ideal_cycle_ms > 0 and run_time_ms > 0:
            performance = min(
                1.0, (cycles_completed * ideal_cycle_ms) / run_time_ms
            )
        else:
            performance = 0.0

        total_cycles = cycles_completed + cycles_aborted
        quality = cycles_completed / total_cycles if total_cycles > 0 else 1.0

        oee = availability * performance * quality

        return cls(
            machine_id=machine_id,
            window_start=window_start,
            window_end=window_end,
            cycles_completed=cycles_completed,
            cycles_aborted=cycles_aborted,
            run_time_ms=run_time_ms,
            planned_time_ms=planned_time_ms,
            ideal_cycle_ms=ideal_cycle_ms,
            availability=availability,
            performance=performance,
            quality=quality,
            oee=oee,
        )


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventCategory(str, Enum):
    """Pillar 3 event categories. Operator-friendly taxonomy."""

    ALARM = "alarm"            # PLC-raised alarm
    ANOMALY = "anomaly"        # Cycle Variance threshold cross (F-003)
    STATUS = "status"          # Machine state change
    DOWNTIME = "downtime"      # Operator-tagged stoppage reason
    INFO = "info"              # General log entry


# Standard downtime reasons — operator picks one from the PWA tablet HMI.
# Customer can extend per-pack via YAML in Phase 4 (machine config).
DOWNTIME_REASONS: tuple[str, ...] = (
    "material_out",
    "setup_changeover",
    "quality_stop",
    "mechanical_breakdown",
    "electrical_fault",
    "operator_break",
    "planned_maintenance",
    "unknown",
)


@dataclass
class EventLogEntry:
    """One row in the Pillar 3 event log.

    Persisted to the `events` table. Surfaced via
    `GET /api/machines/{id}/events` and pushed to PWA clients via the
    WebSocket fan-out (event_type='alarm' or 'event').
    """

    machine_id: str
    timestamp: datetime
    severity: EventSeverity
    category: EventCategory
    code: str = ""
    message: str = ""
    payload: dict = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None
    id: int | None = None  # filled by storage on insert


class LogbookEntryType(str, Enum):
    """Machine logbook entry types — maintenance, notes, tasks, docs."""

    NOTE = "note"
    MAINTENANCE = "maintenance"
    TASK = "task"
    DOCUMENT = "document"
    INCIDENT = "incident"


@dataclass
class LogbookEntry:
    """One entry in the per-machine logbook (F-006 — competitive gap vs Schneider).

    Maintenance notes, task management, document references per machine.
    Persisted to the `logbook` table. Surfaced via
    ``GET /api/machines/{id}/logbook``.
    """

    machine_id: str
    entry_type: LogbookEntryType
    title: str
    body: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)  # filenames / URLs
    resolved: bool = False
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    id: int | None = None  # filled by storage on insert


@dataclass
class CycleStats:
    """Rolling per-step statistics — Welford's online algorithm.

    `stdev_ms` uses the sample standard deviation (n-1). `cv_pct` is the
    coefficient of variation (sigma / mean) expressed as a percentage —
    the headline KPI per F-003.
    """

    machine_id: str
    step_index: int
    step_name: str

    count: int = 0
    avg_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    _m2: float = 0.0  # internal: sum of squared deviations from mean
    stdev_ms: float = 0.0
    cv_pct: float = 0.0  # coefficient of variation (sigma / mean * 100)

    last_updated: datetime = field(default_factory=_utc_now)

    def update(self, sample_ms: float) -> None:
        """Welford's online algorithm — single-pass mean/variance."""
        self.count += 1
        delta = sample_ms - self.avg_ms
        self.avg_ms += delta / self.count
        delta2 = sample_ms - self.avg_ms
        self._m2 += delta * delta2

        if sample_ms < self.min_ms:
            self.min_ms = sample_ms
        if sample_ms > self.max_ms:
            self.max_ms = sample_ms

        if self.count >= 2:
            variance = self._m2 / (self.count - 1)
            self.stdev_ms = variance**0.5
            self.cv_pct = (self.stdev_ms / self.avg_ms * 100.0) if self.avg_ms > 0 else 0.0
        else:
            self.stdev_ms = 0.0
            self.cv_pct = 0.0

        self.last_updated = _utc_now()
