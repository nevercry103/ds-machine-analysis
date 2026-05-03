"""HTTP client for the desktop UI — sync wrapper around the FastAPI backend.

The PyQt6 main thread cannot easily share an asyncio loop with uvicorn,
so the desktop hits its own embedded server (or a remote one) over loopback
HTTP using `httpx.Client`. Every page in the desktop UI consumes the same
endpoints the PWA does — this module is the single boundary.

Architecture rule (CLAUDE.md §9): UI must NOT bypass the API. No direct
storage, registry, or bus access from `ui/`.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class MachineSummary:
    """Trimmed mirror of `api.schemas.machine.MachineSummary` for desktop use.

    We deliberately don't import the FastAPI Pydantic class so the UI
    package doesn't pull FastAPI into the Qt event loop's import graph.
    """

    id: str
    name: str
    status: str
    enabled: bool
    last_cycle_ms: int | None
    last_cycle_id: int | None
    cycle_count: int
    max_cv_pct: float | None


@dataclass(frozen=True)
class StepSummary:
    index: int
    name: str
    duration_ms: int


@dataclass(frozen=True)
class CycleSummary:
    machine_id: str
    cycle_id: int
    total_ms: int
    steps: list[StepSummary]
    bottleneck_step_index: int | None
    max_cv_pct: float | None


@dataclass(frozen=True)
class OEESnapshot:
    """Mirror of `api.schemas.machine.OEEResponse`."""

    machine_id: str
    availability: float
    performance: float
    quality: float
    oee: float
    window_minutes: int
    cycles_completed: int
    cycles_aborted: int


@dataclass(frozen=True)
class EventEntry:
    """Mirror of `api.schemas.machine.EventLogResponse`."""

    id: int
    machine_id: str
    timestamp: str
    severity: str
    category: str
    code: str
    message: str
    acknowledged: bool


@dataclass(frozen=True)
class StepStats:
    """Mirror of the /stats endpoint response."""

    step_index: int
    step_name: str
    count: int
    avg_ms: float
    min_ms: float | None
    max_ms: float
    stdev_ms: float
    cv_pct: float


@dataclass(frozen=True)
class ReplayStep:
    """One step in a replay — includes tag values snapshot."""

    index: int
    name: str
    duration_ms: int
    started_at: str
    ended_at: str
    tag_values: dict


@dataclass(frozen=True)
class CycleReplay:
    """Full replay of a past cycle — engineer scrubs through steps."""

    machine_id: str
    cycle_id: int
    total_ms: int
    steps: list[ReplayStep]
    replay_tag_count: int


class ApiClient:
    """Thin sync HTTP client. Re-uses one `httpx.Client` for keep-alive."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- health / readiness ----------------------------------------------

    def health(self) -> dict:
        return self._get_json("/api/health")

    def ready(self) -> dict:
        return self._get_json("/api/ready")

    # ---- machines --------------------------------------------------------

    def list_machines(self) -> list[MachineSummary]:
        rows = self._get_json("/api/machines")
        return [_parse_machine(row) for row in rows]

    def get_machine(self, machine_id: str) -> MachineSummary:
        return _parse_machine(self._get_json(f"/api/machines/{machine_id}"))

    def get_recent_cycles(self, machine_id: str, limit: int = 20) -> list[CycleSummary]:
        rows = self._get_json(
            f"/api/machines/{machine_id}/cycles", params={"limit": limit}
        )
        return [_parse_cycle(row) for row in rows]

    # ---- OEE (Pillar 2) -------------------------------------------------

    def get_oee(self, machine_id: str) -> OEESnapshot:
        row = self._get_json(f"/api/machines/{machine_id}/oee")
        return OEESnapshot(
            machine_id=row["machine_id"],
            availability=float(row.get("availability", 0)),
            performance=float(row.get("performance", 0)),
            quality=float(row.get("quality", 0)),
            oee=float(row.get("oee", 0)),
            window_minutes=int(row.get("window_minutes", 60)),
            cycles_completed=int(row.get("cycles_completed", 0)),
            cycles_aborted=int(row.get("cycles_aborted", 0)),
        )

    # ---- Events (Pillar 3) ----------------------------------------------

    def get_events(self, machine_id: str, limit: int = 50) -> list[EventEntry]:
        rows = self._get_json(
            f"/api/machines/{machine_id}/events", params={"limit": limit}
        )
        return [
            EventEntry(
                id=int(r.get("id", 0)),
                machine_id=r["machine_id"],
                timestamp=r.get("timestamp", ""),
                severity=r.get("severity", "info"),
                category=r.get("category", "info"),
                code=r.get("code", ""),
                message=r.get("message", ""),
                acknowledged=bool(r.get("acknowledged", False)),
            )
            for r in rows
        ]

    # ---- Replay Mode (F-005) --------------------------------------------

    def get_cycle_replay(self, machine_id: str, cycle_id: int) -> CycleReplay:
        row = self._get_json(f"/api/machines/{machine_id}/cycles/{cycle_id}/replay")
        return CycleReplay(
            machine_id=row["machine_id"],
            cycle_id=int(row["cycle_id"]),
            total_ms=int(row.get("total_ms", 0)),
            steps=[
                ReplayStep(
                    index=int(s["index"]),
                    name=s.get("name", f"Step {s['index']}"),
                    duration_ms=int(s.get("duration_ms", 0)),
                    started_at=s.get("started_at", ""),
                    ended_at=s.get("ended_at", ""),
                    tag_values=s.get("tag_values", {}),
                )
                for s in row.get("steps", [])
            ],
            replay_tag_count=int(row.get("replay_tag_count", 0)),
        )

    # ---- Step stats ------------------------------------------------------

    def get_step_stats(self, machine_id: str) -> list[StepStats]:
        rows = self._get_json(f"/api/machines/{machine_id}/stats")
        return [
            StepStats(
                step_index=int(r.get("step_index", 0)),
                step_name=r.get("step_name", ""),
                count=int(r.get("count", 0)),
                avg_ms=float(r.get("avg_ms", 0)),
                min_ms=r.get("min_ms"),
                max_ms=float(r.get("max_ms", 0)),
                stdev_ms=float(r.get("stdev_ms", 0)),
                cv_pct=float(r.get("cv_pct", 0)),
            )
            for r in rows
        ]

    # ---- internals -------------------------------------------------------

    def _get_json(self, path: str, **kwargs: object) -> dict | list:
        try:
            resp = self._client.get(path, **kwargs)  # type: ignore[arg-type]
        except httpx.HTTPError as exc:
            raise ApiError(f"GET {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ApiError(
                f"GET {path} -> HTTP {resp.status_code}: {resp.text[:200]}",
                status=resp.status_code,
            )
        return resp.json()


def _parse_machine(row: dict) -> MachineSummary:
    return MachineSummary(
        id=row["id"],
        name=row.get("name", row["id"]),
        status=row.get("status", "offline"),
        enabled=bool(row.get("enabled", True)),
        last_cycle_ms=row.get("last_cycle_ms"),
        last_cycle_id=row.get("last_cycle_id"),
        cycle_count=int(row.get("cycle_count", 0)),
        max_cv_pct=row.get("max_cv_pct"),
    )


def _parse_cycle(row: dict) -> CycleSummary:
    return CycleSummary(
        machine_id=row["machine_id"],
        cycle_id=int(row["cycle_id"]),
        total_ms=int(row.get("total_ms", 0)),
        steps=[
            StepSummary(
                index=int(s["index"]),
                name=s.get("name", f"Step {s['index']}"),
                duration_ms=int(s.get("duration_ms", 0)),
            )
            for s in row.get("steps", [])
        ],
        bottleneck_step_index=row.get("bottleneck_step_index"),
        max_cv_pct=row.get("max_cv_pct"),
    )
