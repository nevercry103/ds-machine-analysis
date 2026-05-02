"""SQLite storage backend — Mode 3 (engineering / laptop).

Zero setup, portable, suitable for commissioning and development.
Uses SQLAlchemy 2.0 async ORM over `aiosqlite`.

Architecture layer: STORAGE LAYER
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.data_model import (
    CycleLog,
    CycleStats,
    CycleStatus,
    EventCategory,
    EventLogEntry,
    EventSeverity,
    OEESnapshot,
    StepLog,
    StepStatus,
)
from utils.logger import log

from .base_storage import BaseStorage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CycleLogORM(Base):
    __tablename__ = "cycle_logs"
    __table_args__ = (
        UniqueConstraint("machine_id", "cycle_id", name="uq_cycle_machine_cycle"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cycle_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timestamp_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)

    steps: Mapped[List["StepLogORM"]] = relationship(
        "StepLogORM",
        back_populates="cycle",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class StepLogORM(Base):
    __tablename__ = "step_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(Integer, ForeignKey("cycle_logs.id", ondelete="CASCADE"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timestamp_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Replay Mode (F-005): JSON dict {tag_name: value} captured at the
    # step boundary. Always a dict — empty when replay is disabled.
    tag_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    cycle: Mapped[CycleLogORM] = relationship("CycleLogORM", back_populates="steps")


class OEESnapshotORM(Base):
    """Pillar 2 — one row per rolling-window OEE snapshot."""

    __tablename__ = "oee_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    cycles_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycles_aborted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    planned_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ideal_cycle_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    availability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    performance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    oee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now
    )


class EventLogORM(Base):
    """Pillar 3 — alarm / anomaly / downtime / status events."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    message: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    acknowledged_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CycleStatsORM(Base):
    __tablename__ = "cycle_stats"
    __table_args__ = (
        UniqueConstraint("machine_id", "step_index", name="uq_stats_machine_step"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stdev_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cv_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class SqliteStorage(BaseStorage):
    """
    SQLite storage backend for Mode 3 (laptop).
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        log.info("SqliteStorage initialized", db_path=str(self.db_path))

    async def connect(self) -> bool:
        if self._engine is not None:
            return True

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{self.db_path.as_posix()}"
        self._engine = create_async_engine(database_url, echo=False, future=True)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        log.info("SQLite database initialized", db_path=str(self.db_path))
        return True

    async def disconnect(self) -> bool:
        if self._engine is None:
            return True

        await self._engine.dispose()
        self._engine = None
        self._session_factory = None
        log.info("SQLite database connection closed")
        return True

    async def save_cycle(self, cycle: CycleLog) -> bool:
        """Persist a cycle and its steps.

        Uses SQLite ``INSERT ... ON CONFLICT DO NOTHING`` against the
        ``UNIQUE(machine_id, cycle_id)`` constraint so a duplicate cycle
        (e.g. handshake retry, simulator restart with stale DB) is
        silently skipped with a warning rather than crashing the
        adapter loop. Returns ``False`` when the row was a duplicate.
        """
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")

        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    sqlite_insert(CycleLogORM)
                    .values(
                        machine_id=cycle.machine_id,
                        cycle_id=cycle.cycle_id,
                        timestamp_start=cycle.timestamp_start,
                        timestamp_end=cycle.timestamp_end,
                        total_duration_ms=cycle.total_duration_ms,
                        status=cycle.status.value,
                        created_at=cycle.created_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["machine_id", "cycle_id"]
                    )
                    .returning(CycleLogORM.id)
                )
                result = await session.execute(stmt)
                inserted_pk = result.scalar()

                if inserted_pk is None:
                    log.warning(
                        "Duplicate cycle ignored",
                        machine_id=cycle.machine_id,
                        cycle_id=cycle.cycle_id,
                    )
                    return False

                session.add_all(
                    StepLogORM(
                        cycle_id=inserted_pk,
                        step_index=step.step_index,
                        step_name=step.step_name,
                        timestamp_start=step.timestamp_start,
                        timestamp_end=step.timestamp_end,
                        duration_ms=step.duration_ms,
                        status=step.status.value,
                        tag_values=dict(step.tag_values),
                    )
                    for step in cycle.steps
                )

        log.info(
            "Saved cycle",
            machine_id=cycle.machine_id,
            cycle_id=cycle.cycle_id,
            step_count=len(cycle.steps),
        )
        return True

    async def get_last_cycle_id(self, machine_id: str) -> int:
        """Return ``MAX(cycle_id)`` for a machine, or 0 if none stored."""
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            stmt = select(func.max(CycleLogORM.cycle_id)).where(
                CycleLogORM.machine_id == machine_id
            )
            result = await session.execute(stmt)
            value = result.scalar()
            return int(value) if value is not None else 0

    async def get_cycle(self, machine_id: str, cycle_id: int) -> Optional[CycleLog]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")

        async with self._session_factory() as session:
            statement = select(CycleLogORM).where(
                CycleLogORM.machine_id == machine_id,
                CycleLogORM.cycle_id == cycle_id,
            )
            result = await session.execute(statement)
            orm_cycle = result.scalars().first()
            if orm_cycle is None:
                return None
            return self._to_cycle_log(orm_cycle)

    async def get_cycles(self, machine_id: str, limit: int = 100) -> List[CycleLog]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")

        async with self._session_factory() as session:
            statement = (
                select(CycleLogORM)
                .where(CycleLogORM.machine_id == machine_id)
                .order_by(CycleLogORM.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(statement)
            return [self._to_cycle_log(item) for item in result.scalars().all()]

    async def save_step_stats(self, stats: CycleStats) -> bool:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")

        async with self._session_factory() as session:
            async with session.begin():
                statement = select(CycleStatsORM).where(
                    CycleStatsORM.machine_id == stats.machine_id,
                    CycleStatsORM.step_index == stats.step_index,
                )
                result = await session.execute(statement)
                existing = result.scalars().first()
                if existing is None:
                    existing = CycleStatsORM(
                        machine_id=stats.machine_id,
                        step_index=stats.step_index,
                        step_name=stats.step_name,
                        count=stats.count,
                        avg_ms=stats.avg_ms,
                        min_ms=stats.min_ms if stats.min_ms != float("inf") else 0.0,
                        max_ms=stats.max_ms,
                        stdev_ms=stats.stdev_ms,
                        cv_pct=stats.cv_pct,
                        last_updated=stats.last_updated,
                    )
                    session.add(existing)
                else:
                    existing.step_name = stats.step_name
                    existing.count = stats.count
                    existing.avg_ms = stats.avg_ms
                    existing.min_ms = (
                        stats.min_ms if stats.min_ms != float("inf") else 0.0
                    )
                    existing.max_ms = stats.max_ms
                    existing.stdev_ms = stats.stdev_ms
                    existing.cv_pct = stats.cv_pct
                    existing.last_updated = stats.last_updated
        log.debug(
            "Saved step stats",
            machine_id=stats.machine_id,
            step_index=stats.step_index,
        )
        return True

    async def get_step_stats(
        self,
        machine_id: str,
        step_index: int
    ) -> Optional[CycleStats]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")

        async with self._session_factory() as session:
            statement = select(CycleStatsORM).where(
                CycleStatsORM.machine_id == machine_id,
                CycleStatsORM.step_index == step_index,
            )
            result = await session.execute(statement)
            existing = result.scalars().first()
            if existing is None:
                return None
            return CycleStats(
                machine_id=existing.machine_id,
                step_index=existing.step_index,
                step_name=existing.step_name,
                count=existing.count,
                avg_ms=existing.avg_ms,
                min_ms=existing.min_ms,
                max_ms=existing.max_ms,
                stdev_ms=existing.stdev_ms,
                cv_pct=existing.cv_pct,
                last_updated=existing.last_updated,
            )

    # ------------------------------------------------------------------
    # Pillar 2 — OEE
    # ------------------------------------------------------------------
    async def save_oee_snapshot(self, snapshot: OEESnapshot) -> bool:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    OEESnapshotORM(
                        machine_id=snapshot.machine_id,
                        window_start=snapshot.window_start,
                        window_end=snapshot.window_end,
                        cycles_completed=snapshot.cycles_completed,
                        cycles_aborted=snapshot.cycles_aborted,
                        run_time_ms=snapshot.run_time_ms,
                        planned_time_ms=snapshot.planned_time_ms,
                        ideal_cycle_ms=snapshot.ideal_cycle_ms,
                        availability=snapshot.availability,
                        performance=snapshot.performance,
                        quality=snapshot.quality,
                        oee=snapshot.oee,
                    )
                )
        return True

    async def get_recent_oee(
        self, machine_id: str, limit: int = 100
    ) -> List[OEESnapshot]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            stmt = (
                select(OEESnapshotORM)
                .where(OEESnapshotORM.machine_id == machine_id)
                .order_by(OEESnapshotORM.window_end.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [
                OEESnapshot(
                    machine_id=row.machine_id,
                    window_start=row.window_start,
                    window_end=row.window_end,
                    cycles_completed=row.cycles_completed,
                    cycles_aborted=row.cycles_aborted,
                    run_time_ms=row.run_time_ms,
                    planned_time_ms=row.planned_time_ms,
                    ideal_cycle_ms=row.ideal_cycle_ms,
                    availability=row.availability,
                    performance=row.performance,
                    quality=row.quality,
                    oee=row.oee,
                )
                for row in result.scalars().all()
            ]

    # ------------------------------------------------------------------
    # Pillar 3 — Event Log
    # ------------------------------------------------------------------
    async def save_event(self, event: EventLogEntry) -> EventLogEntry:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            async with session.begin():
                row = EventLogORM(
                    machine_id=event.machine_id,
                    timestamp=event.timestamp,
                    severity=event.severity.value,
                    category=event.category.value,
                    code=event.code,
                    message=event.message,
                    payload=dict(event.payload),
                    acknowledged=event.acknowledged,
                    acknowledged_by=event.acknowledged_by,
                    acknowledged_at=event.acknowledged_at,
                )
                session.add(row)
                await session.flush()
                event.id = row.id
        return event

    async def get_events(
        self,
        machine_id: str,
        limit: int = 100,
        severity: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[EventLogEntry]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            stmt = (
                select(EventLogORM)
                .where(EventLogORM.machine_id == machine_id)
                .order_by(EventLogORM.timestamp.desc())
                .limit(limit)
            )
            if severity is not None:
                stmt = stmt.where(EventLogORM.severity == severity.lower())
            if category is not None:
                stmt = stmt.where(EventLogORM.category == category.lower())
            result = await session.execute(stmt)
            return [self._to_event(row) for row in result.scalars().all()]

    async def acknowledge_event(
        self, event_id: int, *, acknowledged_by: str
    ) -> Optional[EventLogEntry]:
        if self._session_factory is None:
            raise RuntimeError("SQLite storage is not connected")
        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(EventLogORM).where(EventLogORM.id == event_id)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row is None:
                    return None
                row.acknowledged = True
                row.acknowledged_by = acknowledged_by
                row.acknowledged_at = _utc_now()
            return self._to_event(row)

    @staticmethod
    def _to_event(row: EventLogORM) -> EventLogEntry:
        return EventLogEntry(
            id=row.id,
            machine_id=row.machine_id,
            timestamp=row.timestamp,
            severity=EventSeverity(row.severity),
            category=EventCategory(row.category),
            code=row.code,
            message=row.message,
            payload=dict(row.payload or {}),
            acknowledged=row.acknowledged,
            acknowledged_by=row.acknowledged_by,
            acknowledged_at=row.acknowledged_at,
        )

    @staticmethod
    def _to_cycle_log(orm_cycle: CycleLogORM) -> CycleLog:
        return CycleLog(
            cycle_id=orm_cycle.cycle_id,
            machine_id=orm_cycle.machine_id,
            timestamp_start=orm_cycle.timestamp_start,
            timestamp_end=orm_cycle.timestamp_end,
            steps=[
                StepLog(
                    step_index=step.step_index,
                    step_name=step.step_name,
                    timestamp_start=step.timestamp_start,
                    timestamp_end=step.timestamp_end,
                    duration_ms=step.duration_ms,
                    status=StepStatus(step.status),
                    tag_values=dict(step.tag_values or {}),
                )
                for step in sorted(orm_cycle.steps, key=lambda s: s.step_index)
            ],
            total_duration_ms=orm_cycle.total_duration_ms,
            status=CycleStatus(orm_cycle.status),
            created_at=orm_cycle.created_at,
        )
