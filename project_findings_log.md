# Project Findings Log — DS Machine Analyzer

Append-only log of architectural decisions, issues discovered, and design pivots.
Mirrors the convention used in `ds-vision/project_findings_log.md`.

**Format:** Each finding is an `F-NNN` entry with `Status`, `Phase`, `Date`, `Context`, `Decision/Action`.
Never edit a closed finding — open a new one if the decision changes.

---

## F-001 — API-first + PWA architecture (Day 1, not Phase 4)

| Field | Value |
|---|---|
| Status | OPEN |
| Phase | 1 |
| Date | 2026-05-02 |
| Author | Ha + Claude Code |

**Context.** Initial roadmap (v1.0) treated mobile/web access as a Phase 4 concern. Architectural review (this session) flagged that:
- Operators on tablets at machine,
- Engineers on phone walking factory floor,
- Managers on phone receiving push alerts,
- Executives on phone reviewing OEE summary

— all need access to the same backend with role-filtered views. Bolting an API on later means rewriting `core/` to remove direct UI imports — costly. Doing it Day 1 is cheap.

**Decision.**
- FastAPI is the platform's spine. PyQt6 desktop is **one consumer** of the API, alongside the PWA web HMI, CLI, and 3rd-party MES.
- WebSocket fan-out for live events; HTTP for queries; JWT scopes for role gating.
- PWA chosen over native iOS/Android — single codebase, no App Store gate, instant updates, 95% of native capability via Web Push + Service Worker + Web App Manifest.
- HTMX + Tailwind preferred over SvelteKit for simplicity (SME factory tool).

**Action.**
- [x] Add `api/` and `web/` to repo skeleton.
- [x] Promote API + PWA scaffold to Phase 1 exit criteria (`docs/DS-P005-SYS-001_Roadmap.md`).
- [x] Add fastapi, uvicorn, python-jose, jinja2 to `requirements.txt`.
- [x] Wire MachineRegistry into FastAPI lifespan handler (`api/main.py:_lifespan`).
- [x] Implement WebSocket fan-out from Data Bus (`api/state.py:WSHub` + `_make_ws_forwarder`).
- [x] PyQt6 desktop refactor: consume `/api/machines` via `ui/api_client.py` — UI never imports core/storage.

**Status.** All Phase 1 actions closed; finding remains OPEN until Phase 4 swaps the JWT stub for real signing (the only carve-out called out in §4 of the roadmap).

**Cross-reference.** Memory: `feedback_api_first_pwa.md`.

---

## F-002 — Renamed `protocols/` to `plc/` for cross-product consistency

| Field | Value |
|---|---|
| Status | CLOSED |
| Phase | 1 |
| Date | 2026-05-02 |
| Author | Claude Code |

**Context.** ds-vision uses `plc/` for protocol drivers. ds-machine-analysis used `protocols/`. Same concept, different name.

**Decision.** Rename `protocols/` -> `plc/`. Engineers moving between products should not relearn folder structure.

**Action.**
- [x] `mv protocols plc`
- [x] No imports referenced `protocols/` yet (verified via grep) — rename is zero-cost
- [x] CLAUDE.md updated

---

## F-003 — Cycle Variance as headline KPI (positioning shift)

| Field | Value |
|---|---|
| Status | OPEN |
| Phase | 2 |
| Date | 2026-05-02 |
| Author | Ha + Claude Code |

**Context.** Every OEE platform on the market (Tulip, MachineMetrics, Sight Machine, Siemens MindSphere) markets OEE as the headline metric. OEE is lagging — it tells you yesterday's number.

**Decision.** Position DS Machine Analyzer around **Cycle Variance** (sigma between consecutive cycles, per step) as the headline metric. Variance is leading: when step variance climbs above baseline, downtime typically follows in 2-3 hours. This is the marketing wedge.

OEE remains a Phase 2 deliverable but becomes Pillar 2 (supporting), not the headline.

**Action.**
- [x] Implement variance calculation in `core/cycle_processor.py` (Phase 1) — Welford's algorithm in `CycleStats`, anomaly detection with CV% threshold + latch.
- [x] Add `max_cv_pct` field to `MachineSummary` + `CycleSummary` API schemas — headline KPI visible in machine list and cycle history.
- [x] WebSocket event `cycle_anomaly` when CV% > threshold (8% default) — broadcast via `_BROADCAST_EVENT_TYPES` to all connected clients.
- [ ] Marketing/sales material lead with "predict failure 2-3 hours ahead" (Phase 5).

---

## F-004 — Multi-PLC per logical machine

| Field | Value |
|---|---|
| Status | OPEN |
| Phase | 4 |
| Date | 2026-05-02 |
| Author | Claude Code architectural review |

**Context.** Original architecture: 1 machine = 1 protocol adapter = 1 PLC connection. Real factory machines often have:
- Siemens main + Allen-Bradley auxiliary
- Robot controller + cell PLC
- Drive PLC + safety PLC

**Decision.** Reframe: **1 logical machine = N physical PLCs sharing a unified clock.** Data Bus federates events from multiple adapters into one machine's pillar processing.

This is an architectural commitment to be made now (machine_registry / data_bus / config_model schema), even if first implementation only handles N=1 in Phase 1. Avoids rewrite at Phase 4.

**Action.**
- [x] Update `core/config_model.py` — `protocol` field becomes `protocols: list[ProtocolConfig]` (Phase 1, but still N=1 enforced until Phase 4).
- [ ] Document NTP/PTP synchronization requirement for multi-PLC deployments (Phase 4 prep).
- [ ] Validate clock skew at adapter startup; warn if > 50 ms (Phase 4).

---

## F-005 — Phase 1 close-out: gap pass

| Field | Value |
|---|---|
| Status | CLOSED |
| Phase | 1 |
| Date | 2026-05-02 |
| Author | Claude Code |

**Context.** Audit of Phase 1 exit criteria (DS-P005-SYS-001 §4) against actual code found five remaining gaps after the bulk of the engine, API, and PWA were already in place.

**Gaps found and closed:**
1. PyQt6 widgets were pure stubs — they did not consume the API and would have shipped with `# TODO` in user-facing code (violates F-001's "API is the spine" — UI was effectively bypassing the spine by virtue of doing nothing).
2. `web/static/service-worker.js` precached `/web/js/app.js`, but the live page loaded `/web/js/index.js`. Mismatch caused install-time fetches that didn't reflect the running app.
3. Legacy `web/static/js/app.js` was dead code, fully replaced by `index.js` + `api.js` modules.
4. `/api/ready` returned `{"status":"ready"}` unconditionally — useless for orchestrators.
5. PWA had no install-prompt UX despite the criterion explicitly listing "install prompt".

**Action.**
- [x] Built `ui/api_client.py` (sync httpx wrapper) + `MachineSummary`/`CycleSummary` dataclasses.
- [x] Rewrote `ui/widgets/machine_manager.py` — live machine table with 2 s polling against `/api/machines`.
- [x] Rewrote `ui/widgets/cycle_gantt.py` — `QPainter`-based Gantt with bottleneck-step highlight, fed by `/api/machines/{id}/cycles?limit=1`.
- [x] Rewired `ui/main_window.py` as a splitter (machine list ↔ Gantt) wired through Qt signals; `main.py` threads the runtime port into the UI client so `--port 9000` works end-to-end.
- [x] Made `/api/ready` a real check (lifespan state present + storage `_engine` connected); reports `machines` count and `ws_clients` count.
- [x] Fixed service-worker `STATIC_ASSETS` to match the actual files (`tokens.css`, `index.js`, `machine.js`, `api.js`, `theme.js`, `index.html`, `machine.html`, SVG icon); bumped cache version `v0.1.0` → `v0.1.1`.
- [x] Removed dead `web/static/js/app.js`.
- [x] Added install-prompt button in `index.html` header + `wireInstallPrompt()` handler in `index.js` listening for `beforeinstallprompt` / `appinstalled`.
- [x] Added 4 tests (76 total green): `test_ready` payload shape, `/api/ready` 503 when state missing, ApiClient parse for machines + cycles, ApiClient `ApiError` on 404.
- [x] Updated CLAUDE.md and DS-P005-SYS-001 roadmap exit criteria to ✅.

**Remaining Phase 1 work — explicitly out of scope for this finding:**
- Cycle accuracy ≤10 ms vs. PLC timestamp (100 cycles) — requires real S7-1500 lab session.
- Engineer scans QR → tablet PWA opens single-machine view — requires factory-floor smoke test.
- Real-mode `OpcUaAdapter._read_cycle_log()` UDT_CycleLog parser — wired against pilot S7-1500 firmware.

These three are physical-world validation tasks that can't close from a code-only session. Phase 1 → Phase 2 gate (target 2026-07-02) cannot flip until they do.
