"""Tests for `ui.api_client` — sync HTTP client used by the PyQt6 desktop.

These don't hit a real server: we mount an `httpx.MockTransport` onto the
client so the test exercises the JSON->dataclass conversion path that the
desktop relies on, without touching uvicorn or PyQt.
"""

from __future__ import annotations

import httpx
import pytest

from ui.api_client import ApiClient, ApiError, CycleSummary, MachineSummary


def _make_client(handler) -> ApiClient:
    transport = httpx.MockTransport(handler)
    client = ApiClient(base_url="http://test")
    client._client.close()  # noqa: SLF001 — replace the keep-alive client
    client._client = httpx.Client(transport=transport, base_url="http://test")  # noqa: SLF001
    return client


def test_list_machines_parses_dataclasses():
    payload = [
        {
            "id": "m1",
            "name": "Filler 1",
            "enabled": True,
            "status": "idle",
            "protocol_type": "opcua",
            "last_cycle_ms": 1234,
            "last_cycle_id": 42,
            "cycle_count": 7,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/machines"
        return httpx.Response(200, json=payload)

    api = _make_client(handler)
    machines = api.list_machines()
    assert len(machines) == 1
    m = machines[0]
    assert isinstance(m, MachineSummary)
    assert m.id == "m1"
    assert m.last_cycle_ms == 1234
    assert m.cycle_count == 7


def test_get_recent_cycles_parses_steps_and_bottleneck():
    cycle = {
        "machine_id": "m1",
        "cycle_id": 5,
        "started_at": "2026-05-02T10:00:00Z",
        "ended_at": "2026-05-02T10:00:01Z",
        "total_ms": 1000,
        "steps": [
            {
                "index": 1,
                "name": "Load",
                "duration_ms": 300,
                "started_at": "2026-05-02T10:00:00Z",
                "ended_at": "2026-05-02T10:00:00.300Z",
            },
            {
                "index": 2,
                "name": "Press",
                "duration_ms": 700,
                "started_at": "2026-05-02T10:00:00.300Z",
                "ended_at": "2026-05-02T10:00:01Z",
            },
        ],
        "bottleneck_step_index": 2,
        "bottleneck_step_ms": 700,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/machines/m1/cycles"
        return httpx.Response(200, json=[cycle])

    api = _make_client(handler)
    cycles = api.get_recent_cycles("m1", limit=1)
    assert len(cycles) == 1
    c: CycleSummary = cycles[0]
    assert c.cycle_id == 5
    assert c.total_ms == 1000
    assert c.bottleneck_step_index == 2
    assert [s.name for s in c.steps] == ["Load", "Press"]
    assert [s.duration_ms for s in c.steps] == [300, 700]


def test_api_error_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "no such machine"})

    api = _make_client(handler)
    with pytest.raises(ApiError) as exc_info:
        api.get_machine("missing")
    assert exc_info.value.status == 404
