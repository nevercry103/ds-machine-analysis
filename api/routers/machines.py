"""Machine resource endpoints — list, get, recent cycles."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from api.schemas.machine import (
    CycleReplay,
    CycleSummary,
    DowntimeRequest,
    EventAckRequest,
    EventLogResponse,
    LogbookCreateRequest,
    LogbookEntryResponse,
    LogbookUpdateRequest,
    MachineSummary,
    OEEResponse,
    StepReplay,
    StepSummary,
)
from api.state import AppState
from core.data_model import DOWNTIME_REASONS, DataBusEvent, LogbookEntry, LogbookEntryType
from core.event_logger import is_known_downtime_reason
from core.machine_registry import MachineHandle

router = APIRouter(prefix="/api/machines", tags=["machines"])


def _state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="App state not initialized")
    return state


def _max_cv_pct(handle: MachineHandle) -> float | None:
    """Highest CV% across all steps — headline Cycle Variance KPI."""
    stats = handle.processor.step_stats
    if not stats:
        return None
    val = max(s.cv_pct for s in stats)
    return round(val, 2) if val > 0 else None


def _summarize(handle: MachineHandle) -> MachineSummary:
    proc = handle.processor
    return MachineSummary(
        id=handle.machine_id,
        name=handle.config.machine_name,
        enabled=handle.config.enabled,
        status=handle.status.value,
        protocol_type=handle.config.protocol.type,
        current_cycle_step=None,
        last_cycle_ms=int(proc.last_total_ms) if proc.last_total_ms else None,
        last_cycle_id=proc.last_cycle_id or None,
        cycle_count=proc.cycle_count,
        max_cv_pct=_max_cv_pct(handle),
    )


@router.get("", response_model=list[MachineSummary])
async def list_machines(request: Request) -> list[MachineSummary]:
    state = _state(request)
    return [_summarize(h) for h in state.registry.all()]


@router.get("/{machine_id}", response_model=MachineSummary)
async def get_machine(machine_id: str, request: Request) -> MachineSummary:
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    return _summarize(handle)


@router.get("/{machine_id}/cycles", response_model=list[CycleSummary])
async def list_recent_cycles(
    machine_id: str,
    request: Request,
    limit: int = 100,
) -> list[CycleSummary]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be 1..1000")
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")

    cycles = await state.storage.get_cycles(machine_id, limit=limit)
    max_cv_rounded = _max_cv_pct(handle)

    out: list[CycleSummary] = []
    for cycle in cycles:
        bottleneck_step = max(cycle.steps, key=lambda s: s.duration_ms, default=None)
        out.append(
            CycleSummary(
                machine_id=cycle.machine_id,
                cycle_id=cycle.cycle_id,
                started_at=cycle.timestamp_start,
                ended_at=cycle.timestamp_end,
                total_ms=int(cycle.total_duration_ms),
                steps=[
                    StepSummary(
                        index=s.step_index,
                        name=s.step_name,
                        duration_ms=int(s.duration_ms),
                        started_at=s.timestamp_start,
                        ended_at=s.timestamp_end,
                    )
                    for s in cycle.steps
                ],
                bottleneck_step_index=bottleneck_step.step_index if bottleneck_step else None,
                bottleneck_step_ms=int(bottleneck_step.duration_ms)
                if bottleneck_step
                else None,
                max_cv_pct=max_cv_rounded,
            )
        )
    return out


@router.get("/{machine_id}/cycles/{cycle_id}/replay", response_model=CycleReplay)
async def get_cycle_replay(
    machine_id: str, cycle_id: int, request: Request
) -> CycleReplay:
    """Replay Mode (F-005) — full step-by-step snapshot of a past cycle.

    Returns the same step timing as `/cycles` plus the tag values
    captured at each step boundary. Engineers scrub through this in
    the UI to answer "why was Step 3 slow at 14:22 yesterday?"
    """
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")

    cycle = await state.storage.get_cycle(machine_id, cycle_id)
    if cycle is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cycle {cycle_id} for machine {machine_id!r} not found",
        )

    tag_count = sum(len(s.tag_values) for s in cycle.steps)
    return CycleReplay(
        machine_id=cycle.machine_id,
        cycle_id=cycle.cycle_id,
        started_at=cycle.timestamp_start,
        ended_at=cycle.timestamp_end,
        total_ms=int(cycle.total_duration_ms),
        steps=[
            StepReplay(
                index=s.step_index,
                name=s.step_name,
                duration_ms=int(s.duration_ms),
                started_at=s.timestamp_start,
                ended_at=s.timestamp_end,
                tag_values=dict(s.tag_values),
            )
            for s in cycle.steps
        ],
        replay_tag_count=tag_count,
    )


@router.get("/{machine_id}/oee", response_model=OEEResponse)
async def get_oee(machine_id: str, request: Request) -> OEEResponse:
    """Pillar 2 — latest rolling-window OEE snapshot."""
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    if handle.oee is None:
        raise HTTPException(
            status_code=409,
            detail=f"OEE is not enabled for {machine_id!r} "
            f"(check oee_analyzer.enabled in YAML and tier features)",
        )
    snap = handle.oee.compute_snapshot()  # always fresh
    return OEEResponse(
        machine_id=snap.machine_id,
        window_start=snap.window_start,
        window_end=snap.window_end,
        window_minutes=int(handle.oee.window.total_seconds() // 60),
        cycles_completed=snap.cycles_completed,
        cycles_aborted=snap.cycles_aborted,
        run_time_ms=snap.run_time_ms,
        planned_time_ms=snap.planned_time_ms,
        ideal_cycle_ms=snap.ideal_cycle_ms,
        availability=snap.availability,
        performance=snap.performance,
        quality=snap.quality,
        oee=snap.oee,
    )


@router.get("/{machine_id}/events", response_model=list[EventLogResponse])
async def list_events(
    machine_id: str,
    request: Request,
    limit: int = 100,
    severity: str | None = None,
    category: str | None = None,
) -> list[EventLogResponse]:
    """Pillar 3 — event log entries for a machine, newest first."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be 1..1000")
    state = _state(request)
    if state.registry.get(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    rows = await state.storage.get_events(
        machine_id, limit=limit, severity=severity, category=category
    )
    return [
        EventLogResponse(
            id=e.id or 0,
            machine_id=e.machine_id,
            timestamp=e.timestamp,
            severity=e.severity.value,
            category=e.category.value,
            code=e.code,
            message=e.message,
            payload=e.payload,
            acknowledged=e.acknowledged,
            acknowledged_by=e.acknowledged_by,
            acknowledged_at=e.acknowledged_at,
        )
        for e in rows
    ]


@router.post(
    "/{machine_id}/events/{event_id}/ack",
    response_model=EventLogResponse,
)
async def acknowledge_event(
    machine_id: str,
    event_id: int,
    body: EventAckRequest,
    request: Request,
) -> EventLogResponse:
    """Operator/engineer acknowledges an event."""
    state = _state(request)
    if state.registry.get(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    updated = await state.storage.acknowledge_event(
        event_id, acknowledged_by=body.acknowledged_by
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return EventLogResponse(
        id=updated.id or 0,
        machine_id=updated.machine_id,
        timestamp=updated.timestamp,
        severity=updated.severity.value,
        category=updated.category.value,
        code=updated.code,
        message=updated.message,
        payload=updated.payload,
        acknowledged=updated.acknowledged,
        acknowledged_by=updated.acknowledged_by,
        acknowledged_at=updated.acknowledged_at,
    )


@router.post("/{machine_id}/downtime", response_model=EventLogResponse)
async def tag_downtime(
    machine_id: str, body: DowntimeRequest, request: Request
) -> EventLogResponse:
    """Operator-as-Sensor — tag the current downtime with a reason.

    Publishes a `downtime_tag` event onto the per-machine Data Bus.
    `EventLogger` (Pillar 3) catches it and persists. Same path as a
    PLC-raised alarm, so all event consumers (storage, WebSocket
    fan-out) handle it uniformly.
    """
    if not is_known_downtime_reason(body.reason):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown downtime reason {body.reason!r}. "
                f"Allowed: {sorted(DOWNTIME_REASONS)}"
            ),
        )
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    if handle.events is None:
        raise HTTPException(
            status_code=409,
            detail=f"Event log is not enabled for {machine_id!r}",
        )

    now = datetime.now(timezone.utc)
    # Snapshot the latest event id before publishing so the read-back
    # below can ignore older rows in a deterministic, timezone-safe way.
    pre_rows = await state.storage.get_events(
        machine_id, limit=1, category="downtime"
    )
    pre_id = pre_rows[0].id if pre_rows else 0

    await handle.bus.publish(
        DataBusEvent(
            machine_id=machine_id,
            event_type="downtime_tag",
            timestamp=now,
            payload={
                "reason": body.reason.lower(),
                "note": body.note,
                "by": body.by,
            },
        )
    )

    # Read it back so the operator's tablet sees the row id immediately.
    # Tiny race: bus dispatch is async; retry briefly.
    import asyncio

    for _ in range(20):
        rows = await state.storage.get_events(
            machine_id, limit=1, category="downtime"
        )
        if rows and (rows[0].id or 0) > pre_id:
            row = rows[0]
            return EventLogResponse(
                id=row.id or 0,
                machine_id=row.machine_id,
                timestamp=row.timestamp,
                severity=row.severity.value,
                category=row.category.value,
                code=row.code,
                message=row.message,
                payload=row.payload,
                acknowledged=row.acknowledged,
                acknowledged_by=row.acknowledged_by,
                acknowledged_at=row.acknowledged_at,
            )
        await asyncio.sleep(0.05)

    raise HTTPException(
        status_code=503,
        detail="Downtime event was published but did not appear in storage in time.",
    )


@router.get("/{machine_id}/downtime/reasons")
async def list_downtime_reasons() -> list[str]:
    """Operator-facing — the standard downtime taxonomy.

    PWA tablet renders these as one-tap buttons.
    """
    return list(DOWNTIME_REASONS)


@router.get("/{machine_id}/stats")
async def step_stats(machine_id: str, request: Request) -> list[dict]:
    """Per-step rolling stats (count, avg, min, max, stdev, CV%)."""
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    return [
        {
            "step_index": s.step_index,
            "step_name": s.step_name,
            "count": s.count,
            "avg_ms": round(s.avg_ms, 2),
            "min_ms": round(s.min_ms, 2) if s.min_ms != float("inf") else None,
            "max_ms": round(s.max_ms, 2),
            "stdev_ms": round(s.stdev_ms, 2),
            "cv_pct": round(s.cv_pct, 2),
        }
        for s in handle.processor.step_stats
    ]


@router.get("/{machine_id}/shifts/stats")
async def shift_stats(
    machine_id: str, request: Request, limit: int = 200
) -> list[dict]:
    """Multi-shift aggregation — cycle counts and avg duration per shift.

    Groups recent cycles by configured shift windows. Returns one entry
    per shift with cycle count, avg total_ms, and the shift time range.
    """
    from core.data_model import resolve_shift

    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be 1..1000")
    state = _state(request)
    handle = state.registry.get(machine_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")

    shifts = handle.config.shifts
    if not shifts:
        return [{"shift": "All day", "start_hour": 0, "end_hour": 0,
                 "cycle_count": handle.processor.cycle_count,
                 "avg_total_ms": round(handle.processor.last_total_ms, 2)
                 if handle.processor.last_total_ms else None}]

    cycles = await state.storage.get_cycles(machine_id, limit=limit)

    # Group by shift
    buckets: dict[str, list[float]] = {s.name: [] for s in shifts}
    buckets["Unscheduled"] = []
    for cycle in cycles:
        hour = cycle.timestamp_start.hour
        shift_name = resolve_shift(shifts, hour)
        buckets.setdefault(shift_name, []).append(cycle.total_duration_ms)

    result = []
    for s in shifts:
        durations = buckets.get(s.name, [])
        result.append({
            "shift": s.name,
            "start_hour": s.start_hour,
            "end_hour": s.end_hour,
            "cycle_count": len(durations),
            "avg_total_ms": round(sum(durations) / len(durations), 2) if durations else None,
        })

    # Include unscheduled if any
    unsched = buckets.get("Unscheduled", [])
    if unsched:
        result.append({
            "shift": "Unscheduled",
            "start_hour": None,
            "end_hour": None,
            "cycle_count": len(unsched),
            "avg_total_ms": round(sum(unsched) / len(unsched), 2),
        })

    return result


# ---- Machine Logbook (F-006 — competitive gap vs Schneider) ----------

_LOGBOOK_TYPES = {t.value for t in LogbookEntryType}


def _logbook_response(entry: LogbookEntry) -> LogbookEntryResponse:
    return LogbookEntryResponse(
        id=entry.id or 0,
        machine_id=entry.machine_id,
        entry_type=entry.entry_type.value,
        title=entry.title,
        body=entry.body,
        author=entry.author,
        tags=list(entry.tags),
        attachments=list(entry.attachments),
        resolved=entry.resolved,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/{machine_id}/logbook", response_model=list[LogbookEntryResponse])
async def list_logbook(
    machine_id: str,
    request: Request,
    limit: int = 100,
    entry_type: str | None = None,
) -> list[LogbookEntryResponse]:
    """Machine logbook — maintenance notes, tasks, documents."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be 1..1000")
    state = _state(request)
    if state.registry.get(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    if entry_type is not None and entry_type not in _LOGBOOK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entry_type {entry_type!r}. Allowed: {sorted(_LOGBOOK_TYPES)}",
        )
    entries = await state.storage.get_logbook_entries(
        machine_id, limit=limit, entry_type=entry_type
    )
    return [_logbook_response(e) for e in entries]


@router.post("/{machine_id}/logbook", response_model=LogbookEntryResponse, status_code=201)
async def create_logbook_entry(
    machine_id: str, body: LogbookCreateRequest, request: Request
) -> LogbookEntryResponse:
    """Create a logbook entry for a machine."""
    if body.entry_type not in _LOGBOOK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entry_type {body.entry_type!r}. Allowed: {sorted(_LOGBOOK_TYPES)}",
        )
    state = _state(request)
    if state.registry.get(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    entry = LogbookEntry(
        machine_id=machine_id,
        entry_type=LogbookEntryType(body.entry_type),
        title=body.title,
        body=body.body,
        author=body.author,
        tags=list(body.tags),
        attachments=list(body.attachments),
    )
    saved = await state.storage.save_logbook_entry(entry)
    return _logbook_response(saved)


@router.patch(
    "/{machine_id}/logbook/{entry_id}",
    response_model=LogbookEntryResponse,
)
async def update_logbook_entry(
    machine_id: str,
    entry_id: int,
    body: LogbookUpdateRequest,
    request: Request,
) -> LogbookEntryResponse:
    """Update a logbook entry (title, body, tags, resolved)."""
    state = _state(request)
    if state.registry.get(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id!r} not found")
    updated = await state.storage.update_logbook_entry(
        entry_id,
        title=body.title,
        body=body.body,
        tags=body.tags,
        attachments=body.attachments,
        resolved=body.resolved,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Logbook entry {entry_id} not found")
    return _logbook_response(updated)
