# Session 1 Handoff — Architecture Alignment + API-first Pivot

**Date:** 2026-05-02
**Participants:** Ha (OT Lead), Claude Code (Opus 4.7)
**Phase:** 1 — Safety, Foundation, API-first

---

## What was decided this session

### 1. Structural alignment to ds-vision conventions
ds-machine-analysis is now a sibling project to ds-vision in the DS ecosystem and should follow the same conventions where they make sense. Adopted:

- Doc naming: `DS-P005-XXX-NNN_*.md` (P003 = Vision, P005 = Machine Analyzer)
- Folder structure: `utils/`, `scripts/`, `resources/`, `packs/`, `commissioning/`
- Findings log: `project_findings_log.md` append-only with `F-NNN` entries
- Sessions log: `docs/sessions/session_N_handoff.md` (this file)
- Pack boundary rule: platform never imports from `packs/`
- pytest.ini extracted from pyproject.toml (matches ds-vision)

### 2. API-first + PWA architecture (F-001)
Major architectural pivot. Original roadmap put API/web at Phase 4. Pushed to Phase 1 because:
- Operators, engineers, managers, executives all need phone/tablet access
- Bolting API on later requires rewriting `core/` to remove UI imports — expensive
- PWA over native: 1 codebase, no App Store gate, 95% of native capability

Tech stack picks: **FastAPI** (async-native), **HTMX + Tailwind** (PWA simplicity), **JWT scopes** (operator/engineer/manager/executive).

### 3. Six innovations identified for competitive moat
Recorded in `DS-P005-SYS-001_Roadmap.md` Section 2:

1. **Cycle Variance** as headline KPI (leading indicator) — F-003
2. **YAML -> SCL/ST PLC code generator** (Phase 2 killer feature)
3. **Replay Mode** — full tag snapshot per cycle, time-travel debugging
4. **Machine Packs** — App Store moat (CNC, bottle filler, robot cell, etc.)
5. **Multi-PLC per logical machine** (architectural commitment, F-004)
6. **Operator-as-Sensor** — tablet HMI one-tap downtime reason

### 4. Architecture refinements
- `protocols/` -> `plc/` rename (F-002, mirrors ds-vision)
- Data Bus = asyncio pub/sub, **per-pillar queue** (no shared bus, no backpressure)
- Storage Phase 4: PostgreSQL + **TimescaleDB extension** (10x query speed for time-series)
- Headless mode = first-class citizen (Raspberry Pi gateway day-1)

---

## What was built this session

### Repository setup
- [x] Git initialized, remote added: `https://github.com/nevercry103/ds-machine-analysis`
- [x] `.gitignore` aligned to ds-vision (Python, IDE, runtime, customer-specific paths)
- [x] `requirements.txt` + `pyproject.toml` extended with FastAPI/uvicorn/python-jose/jinja2/httpx
- [x] `pytest.ini` extracted from pyproject.toml

### Folder skeleton
- [x] `api/` — FastAPI gateway (main.py, routers/, schemas/, middleware/)
- [x] `web/` — PWA frontend (static/manifest.json, service-worker.js, index.html, app.js, style.css)
- [x] `utils/` — logger.py (loguru wrapper), config_loader.py (YAML -> Pydantic)
- [x] `scripts/` — README with planned scripts
- [x] `resources/icons/`, `resources/fonts/`, `resources/translations/` — README
- [x] `packs/_template/` — pack_manifest.json, README
- [x] `commissioning/` — README
- [x] `docs/sessions/` (this file), `docs/_archive/`, `docs/tool_specs/`

### Documentation
- [x] CLAUDE.md rewritten — API-first architecture, key-files table at ds-vision depth
- [x] `docs/DS-P005-SYS-001_Roadmap.md` — v1.1 with API-first integrated, 10 differentiators, 6 innovations
- [x] `docs/DS-P005-SYS-002_Master_Plan.md` — renamed
- [x] `docs/DS-P005-SYS-003_Reliability_Availability_Scalability.md` — renamed
- [x] `docs/DS-P005-SYS-004_Quick_Reference.md` — renamed
- [x] `docs/DS-P005-UI-001_Design_System.md` — renamed
- [x] `docs/DS-P005-UI-002_Information_Architecture.md` — renamed
- [x] `project_findings_log.md` — F-001 (API-first), F-002 (rename), F-003 (Variance), F-004 (multi-PLC)

### Memory (Claude Code persistent)
- [x] `user_profile.md` — Ha's role, PLC fluency, learning Python
- [x] `project_2026_priorities.md` — DS Vision + DS Machine Analyzer are 2026 main builds
- [x] `reference_github.md` — github.com/nevercry103/ pattern
- [x] `feedback_api_first_pwa.md` — non-negotiable architectural decision
- [x] `project_ds_ecosystem.md` — sibling-products positioning

---

## What's next (Phase 1 work — handoff to Session 2)

Priority order:

1. **Wire FastAPI lifespan to MachineRegistry** — `app.state.registry = MachineRegistry(...)` on startup
2. **Implement Data Bus** — `core/data_bus.py` as asyncio pub/sub with per-pillar `asyncio.Queue`
3. **Implement OPC-UA adapter handshake** — `plc/opcua_adapter.py` polls CycleReady flag, reads UDT, publishes to bus, sets CycleReset
4. **SQLite storage** — `storage/sqlite_storage.py` schema for Cycle/Step tables
5. **Cycle Processor** — `core/cycle_processor.py` step stats + variance calculation
6. **Wire WebSocket fan-out** — `api/routers/ws.py` subscribes to bus, forwards to clients
7. **PyQt6 refactor** — main_window calls `httpx` against local API, not direct imports
8. **First end-to-end test** — Siemens S7-1500 -> adapter -> bus -> processor -> SQLite -> API -> PWA on phone

### Hardware blocker
- Need access to S7-1500 with `FB_CycleMaster.scl` loaded for end-to-end test
- Until then, develop against `commissioning/01_opcua_connect_test.py` against any OPC-UA test server (FreeOpcUa or asyncua's own server)

### Open questions for Ha
- Multi-language: ship en + vi day-1, or vi-only first?
- Tier 1 license shape: per-machine or per-instance?
- First customer pilot machine: which PLC + machine class? (Determines the first reference Pack to ship.)

---

## Files touched this session

```
api/                    (created)
web/                    (created)
utils/                  (created)
scripts/README.md       (created)
resources/README.md     (created)
packs/                  (created)
commissioning/README.md (created)
docs/sessions/          (created)
docs/_archive/          (created)
docs/tool_specs/        (created)
plc/                    (renamed from protocols/)

CLAUDE.md               (rewritten)
README.md               (untouched - update next session)
.gitignore              (rewritten)
requirements.txt        (extended)
pyproject.toml          (extended, pytest section removed)
pytest.ini              (created)
project_findings_log.md (created with F-001..F-004)

docs/DS-P005-SYS-001_Roadmap.md    (renamed + rewritten v1.1)
docs/DS-P005-SYS-002_Master_Plan.md (renamed only)
docs/DS-P005-SYS-003_*.md           (renamed only)
docs/DS-P005-SYS-004_*.md           (renamed only)
docs/DS-P005-UI-001_*.md            (renamed only)
docs/DS-P005-UI-002_*.md            (renamed only)
```

---

## Pending review

- README.md still uses old structure — update next session
- Existing source files (`core/`, `ui/`, `storage/`, `tests/`) untouched — they assume direct UI->core access. Refactor to API-first deferred to Phase 1 implementation work.
