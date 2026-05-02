# Session handoff — Phase 1 close-out gap pass

**Date:** 2026-05-02
**Author:** Claude Code (auto mode)
**Branch:** main (uncommitted)
**Tests:** 76 passing

## What changed this session

Closed five Phase 1 gaps identified by the exit-criteria audit. See `project_findings_log.md` F-005 for the full record.

### New files
- [ui/api_client.py](../../ui/api_client.py) — sync httpx wrapper, `MachineSummary` / `CycleSummary` / `StepSummary` dataclasses.
- [tests/test_ui_api_client.py](../../tests/test_ui_api_client.py) — 3 tests using `httpx.MockTransport`.
- [docs/sessions/session_phase1_closeout_handoff.md](session_phase1_closeout_handoff.md) — this file.

### Rewritten
- [ui/widgets/machine_manager.py](../../ui/widgets/machine_manager.py) — live `QTableWidget` polling `/api/machines` every 2 s, emits `machineSelected(str)` Qt signal.
- [ui/widgets/cycle_gantt.py](../../ui/widgets/cycle_gantt.py) — `QPainter`-based Gantt with bottleneck-step highlight, fed by `/api/machines/{id}/cycles?limit=1`.
- [ui/main_window.py](../../ui/main_window.py) — `QSplitter` shell, status-bar API health pill.

### Modified
- [api/routers/health.py](../../api/routers/health.py) — `/api/ready` now checks lifespan state + storage `_engine`, returns 503 when not initialized.
- [main.py](../../main.py) — desktop path threads `--port` into `ApiClient(base_url)` so `--port 9000` works end-to-end.
- [tests/test_api.py](../../tests/test_api.py) — `/api/ready` payload assertions + 503 case.
- [web/static/index.html](../../web/static/index.html) — install button in header.
- [web/static/js/index.js](../../web/static/js/index.js) — `wireInstallPrompt()` listening for `beforeinstallprompt` / `appinstalled`.
- [web/static/service-worker.js](../../web/static/service-worker.js) — corrected `STATIC_ASSETS` (was `app.js`, is now `index.js` + module siblings); cache version `v0.1.0` → `v0.1.1`.
- [CLAUDE.md](../../CLAUDE.md) — Phase 1 checkboxes flipped.
- [docs/DS-P005-SYS-001_Roadmap.md](../DS-P005-SYS-001_Roadmap.md) — Phase 1 exit criteria flipped to ✅.
- [project_findings_log.md](../../project_findings_log.md) — F-001 actions closed; F-005 added.

### Removed
- `web/static/js/app.js` — dead code, fully superseded by `index.js`.

## Phase 1 status

**Code-side: COMPLETE.** All architecture, API, PWA, and UI exit criteria met.

**Validation-side: BLOCKED on physical-world tasks** (cannot close from code):
1. Cycle accuracy ≤10 ms vs. PLC timestamp (100 cycles, lab) — needs S7-1500.
2. Engineer scans QR → tablet PWA opens single-machine view — needs factory floor.
3. Real-mode `OpcUaAdapter._read_cycle_log()` UDT_CycleLog parser — wire against pilot firmware.

Phase 1 → Phase 2 gate (target 2026-07-02) opens once these three close.

## How to verify

```powershell
python -m pytest tests/ -q              # 76 passed
python -c "from api.main import app"    # 22 routes
python main.py                          # desktop + API on http://127.0.0.1:8000
python main.py --headless               # API only
```

Open http://127.0.0.1:8000/web/ for the PWA. The "Install" button appears in the header on Chromium browsers once PWA-install criteria are satisfied (HTTPS or localhost + manifest valid + SW registered).

## Notes for next session

- **F-004 (multi-PLC)** has untouched Phase 1 actions: `protocols: list[ProtocolConfig]` schema migration is still pending. Consider closing in a small, surgical PR before any S7-1500 lab work locks in the single-protocol shape.
- The PyQt6 desktop currently polls `/api/machines` every 2 s. Phase 2 should swap to a `QThread` + `websockets` client subscribing to `/ws/machines/{id}/events` for the live experience the PWA already has.
- Gantt is static (one cycle, no zoom/hover). Phase 3 polish per roadmap §6.
