# CLAUDE.md — DS Machine Analyzer Platform
## API-first PLC analytics — Cycle / OEE / Event Log

---

## 1. What this is

**DS Machine Analyzer** is a generic PLC analytics platform for SME manufacturing — sibling product to **DS Vision Platform** in the DS Automation ecosystem.

### Core value proposition
- 30-50% cheaper than Tulip / MachineMetrics / Sight Machine / Siemens MindSphere
- Multi-brand PLC support: 6 protocols (OPC-UA / Modbus / EtherNet-IP / ADS / MC / FINS)
- **API-first + PWA** — engineer phone, operator tablet, manager phone all work day-1
- **Edge-first** — runs on factory laptop, cloud is optional sync (data sovereignty)
- **PLC code generator** — YAML config → SCL/ST file (the "killer feature")
- Open architecture: customer owns machine configs + packs, no vendor lock-in
- Local support: Vietnamese engineer, fast on-site response

### Target customers
- SME manufacturers (1-50 machines, factory revenue $1-50M USD)
- OT engineers as primary buyer, plant operators as daily users
- Mid-market FMCG, packaging, electronics, automotive parts

### Product positioning
DS Machine Analyzer is a **product**, not a project. Customer deployments (machine configs, packs, replay archives) live in customer-owned repos or local folders, separate from platform code.

### Sibling to DS Vision
Both products share DS ecosystem standards (PyQt6 + YAML + Python 3.11+ + FastAPI). Neither contains the other. Sold standalone or bundled.

---

## 2. Three Pillars

| # | Pillar | Status | Description |
|---|---|---|---|
| 1 | **Cycle Analyzer** | Pilot | Step time, Gantt, bottleneck, **Cycle Variance** (leading indicator) |
| 2 | **OEE Analyzer** | Phase 2 | Availability x Performance x Quality dashboard |
| 3 | **Error & Operation Log** | Phase 2 | PLC alarm + downtime tracking + operator-as-sensor tagging |

### Core rules
- **Machine = atomic unit.** All data/config/dashboards scope per machine.
- **Max 10 machines per instance** (Phase 4 raises ceiling for cloud Mode 1).
- **1 logical machine = N physical PLCs** sharing unified clock (multi-PLC support, Phase 4).
- All 3 pillars consume from **one Data Bus** per machine.
- Adding a step / machine / protocol must NOT require core engine changes.

---

## 3. Current development phase

**Phase 1 — Safety, Foundation, API-first** (Month 1-2, ACTIVE).

Target completion: 2026-07-02.

Exit criteria (from `docs/DS-P005-SYS-001_Roadmap.md`):

**Architecture:**
- [x] Project structure aligned to ds-vision conventions (utils/, scripts/, resources/, packs/, commissioning/, api/, web/)
- [x] Git repo + GitHub remote at `github.com/nevercry103/ds-machine-analysis`
- [x] FastAPI scaffold runs (`uvicorn api.main:app`) + WebSocket scaffold
- [x] Machine Registry managing 1-10 machines
- [x] Data Bus operational (asyncio pub/sub, per-pillar queue)
- [x] OPC-UA adapter with Siemens S7-1500 pilot (simulator mode + real-mode skeleton; UDT_CycleLog parser is the lab milestone)
- [x] SQLite storage working (Mode 3)
- [x] Cycle Processor calculating step stats + variance
- [x] Configuration YAML loader functional (Pydantic-validated)

**API + Web (NEW — promoted from Phase 4 to Phase 1):**
- [x] `GET /api/machines` returns live registry data
- [x] `GET /api/machines/{id}/cycles` queries SQLite
- [x] `WS /ws/machines/{id}/events` streams cycle complete + alarms
- [x] PWA shell loads on phone (manifest + service worker + install prompt)
- [x] JWT scope stub (engineer/operator/manager/executive) — shape only

**UI:**
- [x] PyQt6 UI consumes the **same API** the PWA does (no direct DB query) via `ui/api_client.py`
- [x] Gantt widget renders cycle from API response (QPainter, bottleneck highlighted)

**Validation:**
- [ ] Cycle accuracy <=10ms vs. PLC timestamp (100 cycles)  *requires real S7-1500 lab session*
- [ ] Engineer scans QR -> tablet PWA opens single-machine view  *requires factory-floor smoke test*

See `docs/DS-P005-SYS-001_Roadmap.md` for full 5-phase / 12-month plan.
See `project_findings_log.md` for active issue tracking (F-001+).

---

## 4. Core architecture

```
+-- CONSUMERS ----------------------------------------------+
|  PyQt6 Desktop  |  PWA Web HMI   |  CLI / Headless / MES  |
|  (engineer)     |  (op/eng/mgr)  |  (3rd-party)           |
+--------+--------+--------+-------+-------+----------------+
         |                 |               |
         v                 v               v
+-- API LAYER (FastAPI) -----------------------------------+
|  REST  /api/machines, /api/cycles, /api/packs            |
|  WS    /ws/machines/{id}/events                          |
|  Auth  JWT scopes (operator/engineer/manager/executive)  |
+--------+-------------------------------------------------+
         |
         v
+-- CORE BACKEND (asyncio, pure Python, no Qt) ------------+
|  Machine Registry: lifecycle of 1..10 machines           |
|    +-- Machine: 1 logical = N physical PLCs              |
|         DISCONNECTED -> CONNECTING -> IDLE <-> BUSY      |
|                                  |     |                  |
|                                FAULT <-+                  |
|  Data Bus: asyncio pub/sub, per-pillar queue             |
|    +--> Cycle Processor   -> Pillar 1 (variance + Gantt) |
|    +--> OEE Processor     -> Pillar 2 (stub)             |
|    +--> Event Logger      -> Pillar 3 (stub)             |
|  Pack Loader: discovers packs/ folder                    |
+--------+-------------------------------------------------+
         |
         v
+-- PROTOCOL LAYER (plc/) ---------------------------------+
|  BaseAdapter ABC                                          |
|    +-- opcua_adapter.py    (Siemens / Codesys / Beckhoff)|
|    +-- modbus_adapter.py   (planned)                     |
|    +-- ethernet_ip_adapter.py (planned, Allen-Bradley)   |
|    +-- ads_adapter.py      (planned, Beckhoff TwinCAT)   |
|    +-- mc_protocol_adapter.py (planned, Mitsubishi)      |
+--------+-------------------------------------------------+
         |
         v
+-- STORAGE LAYER -----------------------------------------+
|  BaseStorage ABC                                          |
|    +-- sqlite_storage.py   (Mode 3 - laptop)             |
|    +-- postgres_storage.py (Mode 1 & 2 - server, +Timescale)|
+----------------------------------------------------------+
```

### Design principles

- **API is the spine.** PyQt6, PWA, CLI all consume the same FastAPI endpoints. Core never imports from `ui/` or `web/`.
- **Core is pure Python, no Qt.** Headless-testable; runs on Raspberry Pi gateway with `--headless`.
- **Data Bus = asyncio pub/sub** with per-pillar queues. A slow OEE writer must never backpressure cycle capture.
- **Timestamp at PLC, not Python.** Network latency must not pollute cycle data — accuracy <= 10 ms.
- **Brand-agnostic PLC templates.** Same `FB_CycleMaster` SCL/ST works across all brands; only system-time call + protocol export change.
- **Config over code.** Adding a step / machine = edit YAML, no Python change.
- **Pack boundary.** Platform never imports from `packs/` — packs extend platform, not vice versa.
- **Watchdog auto-restarts FAULT machines** (cooldown 10 s, mirrors ds-vision).
- **Tier gating** at recipe load (Phase 2): refuse to load if license tier < required.

---

## 5. Folder structure

```
ds-machine-analysis/
+-- api/                       <- FastAPI gateway (Day 1, not Phase 4)
|   +-- main.py                <- uvicorn entry, lifespan, CORS, mount routers
|   +-- routers/
|   |   +-- health.py          <- /api/health, /api/ready
|   |   +-- machines.py        <- /api/machines/*
|   |   +-- ws.py              <- /ws/machines/{id}/events
|   +-- schemas/               <- Pydantic wire format (versioned)
|   |   +-- machine.py
|   +-- middleware/
|   |   +-- auth.py            <- JWT scopes stub
|   +-- README.md
|
+-- web/                       <- PWA web HMI (Day 1)
|   +-- static/
|   |   +-- index.html         <- machine grid landing
|   |   +-- manifest.json      <- PWA install metadata
|   |   +-- service-worker.js  <- offline cache + push handler
|   |   +-- css/style.css      <- mobile-first
|   |   +-- js/app.js          <- WS client + grid render
|   +-- templates/             <- Jinja2 templates (htmx)
|   +-- README.md
|
+-- core/                      <- Pure Python engine, no Qt, no FastAPI
|   +-- data_model.py          <- Single source of truth (dataclasses)
|   +-- machine_registry.py    <- 1-10 machines lifecycle
|   +-- data_bus.py            <- asyncio pub/sub (per-pillar queue)
|   +-- cycle_processor.py     <- Pillar 1 (cycle + variance)
|   +-- oee_processor.py       <- Pillar 2 (stub)
|   +-- event_logger.py        <- Pillar 3 (stub)
|   +-- config_model.py        <- Pydantic models for YAML
|   +-- pack_loader.py         <- packs/ discovery (Phase 2)
|
+-- plc/                       <- Protocol adapters (was protocols/)
|   +-- base_adapter.py        <- Abstract base class
|   +-- opcua_adapter.py       <- OPC-UA (pilot)
|   +-- modbus_adapter.py      <- Modbus - stub
|   +-- ethernet_ip_adapter.py <- EtherNet/IP - stub
|   +-- mc_protocol_adapter.py <- Mitsubishi - stub
|   +-- ads_adapter.py         <- Beckhoff - stub
|
+-- plc_templates/             <- OT engineer SCL/ST imports
|   +-- TEMPLATE_STANDARD.md
|   +-- siemens_s7/
|   |   +-- FB_CycleMaster.scl
|   |   +-- README_TIAPortal.md
|   +-- codesys/
|   +-- beckhoff/              <- planned
|   +-- mitsubishi/            <- planned
|
+-- storage/                   <- Storage backends
|   +-- base_storage.py        <- Abstract base class
|   +-- sqlite_storage.py      <- Mode 3 (laptop)
|   +-- postgres_storage.py    <- Mode 1 & 2 (server) - TimescaleDB Phase 4
|
+-- ui/                        <- PyQt6 desktop (one of several API consumers)
|   +-- main_window.py
|   +-- widgets/
|       +-- machine_manager.py
|       +-- cycle_gantt.py
|       +-- oee_dashboard.py   <- stub
|       +-- event_log_view.py  <- stub
|
+-- utils/                     <- Cross-cutting helpers
|   +-- logger.py              <- Loguru wrapper, daily rotation
|   +-- config_loader.py       <- YAML -> Pydantic MachineConfig
|
+-- packs/                     <- Machine type packs (App Store moat)
|   +-- _template/             <- copy + customize
|   +-- README.md              <- pack boundary rule
|
+-- commissioning/             <- On-site bench scripts (numbered 00..NN)
|   +-- README.md
|
+-- scripts/                   <- Developer/build tools
|   +-- README.md
|
+-- resources/                 <- Static assets shared by PyQt6 + PWA
|   +-- icons/
|   +-- fonts/
|   +-- translations/          <- en + vi day-1
|
+-- config/                    <- Machine configs
|   +-- machines/
|   |   +-- machine_001.yaml.sample
|   +-- tier_profiles/         <- Phase 2: tier_1 / tier_5 / tier_unlimited
|
+-- data/                      <- Runtime (gitignored)
|   +-- *.db
|   +-- replay/                <- cycle snapshot archive (Phase 2 Replay Mode)
|   +-- exports/
|
+-- logs/                      <- Application logs (gitignored)
+-- tests/                     <- pytest unit + integration + api
+-- docs/                      <- DS-P005-XXX numbered docs
|   +-- DS-P005-SYS-001_Roadmap.md
|   +-- DS-P005-SYS-002_Master_Plan.md
|   +-- DS-P005-SYS-003_Reliability_Availability_Scalability.md
|   +-- DS-P005-SYS-004_Quick_Reference.md
|   +-- DS-P005-UI-001_Design_System.md
|   +-- DS-P005-UI-002_Information_Architecture.md
|   +-- sessions/              <- per-session handoff (session_N_handoff.md)
|   +-- _archive/
|
+-- project_findings_log.md    <- Active issue tracking (F-001 append-only)
+-- main.py                    <- Entry point (PyQt6 + uvicorn co-hosted)
+-- requirements.txt
+-- pyproject.toml
+-- pytest.ini
+-- .gitignore
+-- CLAUDE.md                  <- this file
+-- README.md
```

---

## 6. Key files

| File | Role |
|---|---|
| **API layer (the spine)** | |
| [api/main.py](api/main.py) | FastAPI app, CORS, lifespan, mount routers |
| [api/routers/machines.py](api/routers/machines.py) | `/api/machines/*` REST endpoints |
| [api/routers/ws.py](api/routers/ws.py) | WebSocket `/ws/machines/{id}/events` for live fan-out |
| [api/schemas/machine.py](api/schemas/machine.py) | `MachineSummary`, `CycleSummary`, `StepSummary` Pydantic wire schemas |
| [api/middleware/auth.py](api/middleware/auth.py) | JWT scopes: operator / engineer / manager / executive |
| **PWA web HMI** | |
| [web/static/index.html](web/static/index.html) | Machine grid landing page |
| [web/static/manifest.json](web/static/manifest.json) | PWA install metadata (DS-MA short_name) |
| [web/static/service-worker.js](web/static/service-worker.js) | Offline cache + push notifications |
| [web/static/js/app.js](web/static/js/app.js) | Bootstrap: fetch /api/machines + WS subscribe per machine |
| [web/static/css/style.css](web/static/css/style.css) | Mobile-first, dark mode via `prefers-color-scheme` |
| **Core (no Qt, no FastAPI)** | |
| [core/data_model.py](core/data_model.py) | Cycle / Step / Machine dataclasses (single source of truth) |
| [core/config_model.py](core/config_model.py) | Pydantic `MachineConfig` for YAML validation |
| [core/machine_registry.py](core/machine_registry.py) | 1-10 machines lifecycle, watchdog |
| [core/data_bus.py](core/data_bus.py) | asyncio pub/sub, per-pillar queue |
| [core/cycle_processor.py](core/cycle_processor.py) | Pillar 1 — step stats + Cycle Variance |
| [core/oee_processor.py](core/oee_processor.py) | Pillar 2 stub |
| [core/event_logger.py](core/event_logger.py) | Pillar 3 stub |
| **Protocol layer** | |
| [plc/base_adapter.py](plc/base_adapter.py) | Abstract base class — all adapters inherit |
| [plc/opcua_adapter.py](plc/opcua_adapter.py) | OPC-UA (Siemens S7-1500 pilot via asyncua) |
| **Storage** | |
| [storage/base_storage.py](storage/base_storage.py) | Abstract async storage interface |
| [storage/sqlite_storage.py](storage/sqlite_storage.py) | Mode 3 (laptop) - aiosqlite |
| [storage/postgres_storage.py](storage/postgres_storage.py) | Mode 1+2 (server) - TimescaleDB extension Phase 4 |
| **PLC templates (OT side)** | |
| [plc_templates/siemens_s7/FB_CycleMaster.scl](plc_templates/siemens_s7/FB_CycleMaster.scl) | Pilot SCL function block |
| [plc_templates/TEMPLATE_STANDARD.md](plc_templates/TEMPLATE_STANDARD.md) | Brand-agnostic template standard |
| **Utils** | |
| [utils/logger.py](utils/logger.py) | Loguru wrapper - daily rotation, env-controlled level |
| [utils/config_loader.py](utils/config_loader.py) | YAML -> Pydantic `MachineConfig` |
| **UI (PyQt6)** | |
| [ui/main_window.py](ui/main_window.py) | Main window - consumes the same API the PWA does |
| [ui/widgets/cycle_gantt.py](ui/widgets/cycle_gantt.py) | Gantt visualization widget |
| **Entry** | |
| [main.py](main.py) | PyQt6 + uvicorn co-hosted entry point |

---

## 7. Configuration

| Where | Purpose |
|---|---|
| [config/machines/machine_001.yaml](config/machines/) | Per-machine: protocol, steps, pillars enabled |
| [config/tier_profiles/](config/tier_profiles/) | Tier feature gating (Phase 2) |
| .env | Runtime: API port, JWT secret, DB connection string |

Environment variables: `DS_MA_LOG_LEVEL`, `DS_MA_LOG_PLAIN`, `DS_MA_API_PORT`, `DS_MA_DB_URL`, `DS_MA_JWT_SECRET`, `DS_MA_CORS_ORIGINS`.

---

## 8. PLC side — OT template standard

### Core principle: timestamp at PLC

Cycle/step timestamps are calculated **on the PLC**, never on Python. Reasons:
- <=10 ms accuracy (network latency would add 5-50 ms variance)
- Survives Python disconnection without losing data
- Matches industrial best practice (PLC is the real-time system)

### Brand-agnostic template

Same `FB_CycleMaster` SCL/ST logic across all brands. Only the system-time call and the protocol export differ.

| PLC Brand | Language | System Time Func | Protocol |
|---|---|---|---|
| Siemens S7-1500/1200 | SCL | `RD_SYS_T()` | OPC-UA built-in |
| Codesys | ST | `GET_DATE_AND_TIME()` | OPC-UA / Modbus |
| Beckhoff TwinCAT | ST | `F_GetSystemTime()` | ADS / OPC-UA |
| Mitsubishi iQ-R/F | ST | `SD210-SD213` | MC Protocol |
| Allen-Bradley | ST | `GSV` | EtherNet/IP |
| OMRON | ST | `GetSysInfo()` | EtherNet/IP / Modbus |

### Handshake protocol

```
PLC                          Python (adapter)
---                          ----------------
Cycle complete
  -> set CycleReady = TRUE  --> detect flag
                                 read CycleLog data
                                 publish to Data Bus
                            --> set CycleReset = TRUE
  <- clear CycleReady             (acknowledge)
  <- clear CycleReset
```

### Pilot: Siemens S7-1500
- Protocol: OPC-UA built-in (port 4840)
- Template: `plc_templates/siemens_s7/FB_CycleMaster.scl`
- Firmware: >= V2.1 (needs `DTL_DIFF`)

### Future: PLC code generator (Phase 2 killer feature)

```
config/machines/machine_001.yaml
        |
        v
scripts/generate_plc_template.py
        |
        +--> plc_templates_generated/siemens_s7/FB_CycleMaster.scl
        +--> plc_templates_generated/codesys/FB_CycleMaster.st
        +--> plc_templates_generated/beckhoff/FB_CycleMaster.st
```

OT engineer copies generated file into TIA Portal / Codesys / TwinCAT — adding a step in YAML now updates **both sides** of the handshake.

---

## 9. Coding rules

### Must
- Every protocol adapter inherits `plc/base_adapter.py`
- Every storage backend inherits `storage/base_storage.py`
- `core/data_model.py` is the single source of truth for dataclasses — no model definitions elsewhere
- Machine config is YAML, validated through `core/config_model.py` Pydantic schema — no hardcoded machine info
- Every API endpoint has a Pydantic `response_model` from `api/schemas/`
- Async/await for all I/O (OPC-UA, DB, HTTP, WebSocket)
- Every file has a docstring explaining its role in the architecture

### Must Not
- Calculate timestamps on Python — always read from PLC
- Direct connection from `ui/` or `web/` to PLC — must go through API
- Import `ui/` from `core/` or `api/`
- Import `packs/*` from anywhere in the platform (pack boundary rule)
- Serialize `core.data_model` dataclasses directly through the API — always go through `api/schemas/`
- Hardcode IP, tag path, step count, machine ID
- Block the asyncio event loop with sync I/O

### Stubs
- Pillar 2 / 3 / new adapter: file scaffolds with full method signatures, raise `NotImplementedError`, `# TODO Pillar 2` / `# TODO Modbus`

---

## 10. How a cycle runs

```
PLC: cycle complete -> set CycleReady = TRUE
  -> opcua_adapter detects flag (asyncio polling, 100ms tick)
  -> adapter reads UDT_CycleLog from DB_CycleLog
  -> adapter publishes Cycle event to Data Bus
       |
       +--> Cycle Processor:
       |      compute step times, variance, bottleneck
       |      -> publish CycleSummary back to bus
       |
       +--> OEE Processor (Phase 2): increment counters
       +--> Event Logger (Phase 2): scan for alarm tags
  -> adapter sets CycleReset = TRUE (handshake ack)
  -> PLC clears both flags

Storage:
  -> CycleSummary persisted via storage backend (SQLite/Postgres)

API fan-out (parallel):
  -> API WebSocket subscribers receive {type: "cycle_complete", machine_id, total_ms, steps, variance}
  -> All connected clients (PyQt6 desktop + PWA tablets + PWA phones) update simultaneously
```

If recipe (machine config) is empty or missing -> machine state = `FAULT` with message pointing to config. **Platform never falls back to a baked-in pipeline.**

---

## 11. Deployment modes

| Mode | Deployment | Database | Use case |
|---|---|---|---|
| 1 | DS Cloud (multi-tenant) | PostgreSQL + TimescaleDB | SaaS service (Phase 4) |
| 2 | On-Premise (customer site) | PostgreSQL + TimescaleDB | Dedicated server (Phase 4) |
| 3 | Local Laptop | SQLite | Commissioning / engineering (Phase 1) |

Same codebase, mode chosen by `.env` config (`DS_MA_DB_URL`).

---

## 12. Innovations (vs. Tulip / MachineMetrics / Sight Machine)

Documented in `docs/DS-P005-SYS-001_Roadmap.md` Section 2:

1. **Cycle Variance as headline KPI** — leading indicator, predicts failure
2. **YAML -> SCL/ST PLC code generator** — competitors never touch PLC
3. **Replay Mode (time-travel debugging)** — full tag snapshot per cycle
4. **Machine Packs (App Store moat)** — pre-configured bundles per machine type
5. **Multi-PLC per machine** — main + safety + drive PLCs unified
6. **Operator-as-Sensor** — tablet HMI one-tap downtime reason
7. **PWA web HMI day-1** — phone/tablet first-class
8. **Edge-first, cloud-optional** — SME data sovereignty
9. **Brand-agnostic PLC templates** — one logic, all brands
10. **Timestamp at PLC, <=10ms** — network-latency-immune

---

## 13. User & context

**Ha** — OT/Manufacturing engineer at DS Automation (Vietnam).

- Background: industrial automation, conveyor systems, machine vision, IoT
- PLC fluency: Siemens S7-1200 / S7-1500 (TIA Portal, SCL)
- Learning: Python, async, software architecture, PyQt6
- Goal: bridge OT <-> software development; ship products
- Tools: VS Code + Claude Code CLI + TIA Portal

### Workflow
- PLC code: TIA Portal (Ha alone)
- Python code: VS Code + Claude Code (collaboration)
- Test: real S7-1500 hardware, no simulator

### 2026 priorities
DS Vision Platform + DS Machine Analyzer are Ha's two main software products being built with Claude Code through 2026. Sibling products in the DS ecosystem.

---

## 14. Key documents

### Strategic
- `docs/DS-P005-SYS-001_Roadmap.md` — 5-phase 12-month plan with API-first integrated
- `docs/DS-P005-SYS-002_Master_Plan.md` — companion planning guide (team, budget, gates)
- `docs/DS-P005-SYS-003_Reliability_Availability_Scalability.md` — RAS requirements
- `docs/DS-P005-SYS-004_Quick_Reference.md` — cheat sheet
- `project_findings_log.md` — Active issue tracking (F-001+ append-only)

### UI / UX
- `docs/DS-P005-UI-001_Design_System.md` — color, typography, component library
- `docs/DS-P005-UI-002_Information_Architecture.md` — user personas + flows

### Sessions
- `docs/sessions/session_N_handoff.md` — per-session continuity notes

---

## 15. GitHub

- Repo: `https://github.com/nevercry103/ds-machine-analysis`
- Org: `nevercry103` (same as `ds-vision`)
- Default branch: `main`

---

## 16. Python packages

Core: pydantic, asyncua, pymodbus, pycomm3, SQLAlchemy, aiosqlite, psycopg2-binary, PyYAML
API: fastapi, uvicorn[standard], python-multipart, python-jose[cryptography], jinja2
UI: PyQt6, qtawesome, pyqt-toast-notification
Utils: loguru, numpy, Pillow, psutil
Dev: pytest, pytest-asyncio, pytest-cov, httpx, black, mypy, ruff
