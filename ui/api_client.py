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
    )
