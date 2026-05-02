# api/ — FastAPI gateway

The **spine of the platform.** Every consumer (PyQt6 desktop, PWA web
HMI, CLI tools, 3rd-party MES) goes through this layer. Core business
logic stays in `core/`; this folder only does transport + auth + schemas.

## Why API-first

Decision recorded in finding F-001 + memory `feedback_api_first_pwa.md`:

> Operators + engineers + managers all need phone/tablet access to track
> and diagnose machines remotely. PyQt6 alone won't reach them. API-first
> with PWA web HMI is the answer — designed in Day 1, not bolted on later.

PyQt6 is **one consumer** of the API, not the owner. Same for the PWA
web frontend, same for any future tool.

## Run

```bash
# Standalone (development):
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Embedded with PyQt6 desktop:
python main.py    # main.py spins up uvicorn in a thread alongside Qt event loop
```

## Endpoints

| Path | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness probe |
| `/api/ready` | GET | Readiness probe (checks DB, registry) |
| `/api/machines` | GET | List all machines + status |
| `/api/machines/{id}` | GET | One machine + current state |
| `/api/machines/{id}/cycles?limit=N` | GET | Recent cycles for a machine |
| `/ws/machines/{id}/events` | WS | Live cycle/alarm/NG event stream |

API docs auto-generated at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Auth

JWT with role scopes — `operator`, `engineer`, `manager`, `executive`.
Same API, filtered responses per scope.

| Action | Operator | Engineer | Manager | Executive |
|---|:-:|:-:|:-:|:-:|
| View machines + cycles | ✅ | ✅ | ✅ | ✅ |
| Acknowledge alarm | ✅ | ✅ | ❌ | ❌ |
| Tag downtime reason | ✅ | ✅ | ❌ | ❌ |
| Configure machine / steps | ❌ | ✅ | ❌ | ❌ |
| Configure alarm thresholds | ❌ | ✅ | ❌ | ❌ |
| Replay past cycles | ❌ | ✅ | ❌ | ❌ |
| Write PLC values | ❌ | ✅ (with UI confirm) | ❌ | ❌ |
| Export reports | ❌ | ✅ | ✅ | ✅ |
| Analyze downtime trends | ❌ | ✅ | ✅ | ❌ |

Phase 1 stub: defaults to `engineer` if no token. Real JWT validation lands when first multi-role customer ships.

## Structure

```
api/
├── __init__.py
├── main.py              ← FastAPI app, CORS, lifespan, mount routers
├── routers/
│   ├── health.py        ← /api/health, /api/ready
│   ├── machines.py      ← /api/machines/*
│   └── ws.py            ← /ws/machines/{id}/events
├── schemas/             ← Pydantic wire format (versioned)
│   └── machine.py
└── middleware/
    └── auth.py          ← JWT + role-scope decorator
```

## Rules

- ❌ Never import from `ui/`
- ❌ Never serialize `core.data_model` dataclasses directly — always pass through `api.schemas`
- ✅ All handlers async (`async def`) — backend is asyncio-native
- ✅ WebSocket for live events, HTTP for queries
- ✅ Errors as proper HTTP status codes + Pydantic error responses
