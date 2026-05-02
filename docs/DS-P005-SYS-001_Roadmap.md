---
# DS AUTOMATION
## DS Machine Analyzer Platform — Roadmap

---

| Field | Value |
|-------|-------|
| Document | DS Machine Analyzer Platform — Roadmap |
| Doc ID | DS-P005-SYS-001 |
| Version | 1.1 |
| Date | 2026-05-02 |
| Author | Ha (OT Lead) + Claude Code |
| Status | ACTIVE — Phase 1 |
| Confidential | Yes |

### Revision History

| Ver | Date | Changes |
|-----|------|---------|
| 1.0 | 2026-05-02 | Initial 5-phase 12-month plan |
| 1.1 | 2026-05-02 | API-first + PWA architecture (F-001), Cycle Variance headline metric, PLC code generator, Replay Mode, Machine Packs, multi-PLC per machine |

---

## 1. Vision

A professional, user-friendly PLC analytics platform for SME manufacturing — **Reliability, Availability, Scalability** as core pillars, **API-first + PWA** as the access model.

**Three pillars (features):**
1. **Cycle Analyzer** (Pilot) — step time, Gantt, bottleneck, **Cycle Variance**
2. **OEE Analyzer** (Phase 2) — Availability × Performance × Quality
3. **Error & Operation Log** (Phase 2) — PLC alarms + downtime taxonomy

**Three deployment modes (same code):**
1. **DS Cloud** — multi-tenant SaaS (Phase 4)
2. **On-Premise Server** — dedicated customer install (Phase 4)
3. **Local Laptop** — commissioning + engineering (Phase 1)

**Four user roles (different views, same API):**
1. **OT Engineer** — setup, diagnostics, commissioning, replay
2. **Plant Operator** — real-time cycle, downtime tagging
3. **Manufacturing Manager** — bottleneck analysis, OEE, reports
4. **Factory Executive** — high-level OEE dashboard

**Access surfaces:**
- **PyQt6 desktop** — engineer commissioning, full configuration
- **PWA web HMI** — operator tablet, engineer phone, manager phone, executive phone
- **REST + WebSocket API** — backbone of both, plus 3rd-party MES integration
- **CLI / headless mode** — Raspberry Pi gateway deployments

---

## 2. Differentiators (vs. Tulip / MachineMetrics / Sight Machine / Siemens MindSphere)

| # | Differentiator | Why competitors don't have it |
|---|---|---|
| 1 | **Cycle Variance as headline KPI** | Everyone markets OEE (lagging). Variance is leading — predicts failure 2-3h ahead |
| 2 | **YAML → SCL/ST PLC code generator** | Tulip/MachineMetrics never touch the PLC; we ship working PLC code |
| 3 | **Replay Mode (time-travel debugging)** | Full PLC tag snapshot per cycle, scrub through past 24h like a debugger |
| 4 | **Machine Packs (App Store moat)** | Pre-configured bundles for CNC / bottle filler / robot cell — 80% setup done |
| 5 | **Multi-PLC per machine** | Real machines have main + safety + drive PLCs; competitors assume 1:1 |
| 6 | **Operator-as-Sensor** | Tablet HMI: one-tap downtime reason, fuses with PLC events |
| 7 | **PWA web HMI day-1** | Phone/tablet first-class, no native app needed |
| 8 | **Edge-first, cloud-optional** | SME factories distrust cloud; data sovereignty as sales lever |
| 9 | **Brand-agnostic PLC templates** | One `FB_CycleMaster` works across Siemens / Codesys / Beckhoff / Mitsubishi / AB / Omron |
| 10 | **Timestamp at PLC, ≤10ms accuracy** | Network latency never pollutes cycle data |

---

## 3. Phase Timeline

```
Month 1-2   Month 3-4   Month 5-6   Month 7-8   Month 9-12
│ PHASE 1 │  PHASE 2  │  PHASE 3  │  PHASE 4  │  PHASE 5  │
│ SAFETY  │  FEATURES │  POLISH   │  SCALE    │  PRODUCT  │
│ + API   │  + PACKS  │   & UX    │  & CLOUD  │  READY    │
└─────────┴───────────┴───────────┴───────────┴───────────┘
```

---

## 4. Phase 1 — Safety, Foundation, API-first (Month 1-2) 🚧 ACTIVE

**Goal:** Reliable architecture, OPC-UA + S7-1500 pilot, **API-first spine wired in from Day 1**.

### Exit Criteria

**Architecture:**
- ✅ Project structure (DS-vision-aligned: utils, scripts, resources, packs, commissioning, api, web)
- ✅ Git repo + GitHub remote at `github.com/nevercry103/ds-machine-analysis`
- ✅ FastAPI scaffold runs (`uvicorn api.main:app`) + WebSocket scaffold
- ✅ Machine Registry managing 1-10 machines
- ✅ Data Bus operational (asyncio pub/sub, per-pillar queue, drop-on-overflow)
- ✅ OPC-UA adapter with Siemens S7-1500 pilot (simulator mode + real-mode skeleton; UDT_CycleLog parser is the lab milestone)
- ✅ SQLite storage working (Mode 3)
- ✅ Cycle Processor calculating step stats + variance + anomaly emission
- ✅ Configuration YAML loader functional (Pydantic-validated)

**API + Web (NEW — was Phase 4 before):**
- ✅ `GET /api/machines` returns live registry data
- ✅ `GET /api/machines/{id}/cycles` queries SQLite
- ✅ `WS /ws/machines/{id}/events` streams cycle complete + alarms + anomalies
- ✅ PWA shell loads on phone (manifest, service worker, install prompt button wired to `beforeinstallprompt`)
- ✅ JWT scope stub (engineer/operator/manager/executive) — shape only, no real signing
- ✅ `/api/ready` reports live registry + WS-client counts (orchestrator-friendly)

**UI:**
- ✅ Basic PyQt6 UI skeleton consumes the **same API** the PWA does (`ui/api_client.py`)
- ✅ Gantt widget renders cycle from API response — QPainter, bottleneck step highlighted

**Validation:**
- ⏳ Cycle accuracy ≤10ms vs. PLC timestamp (100 cycles, lab) — *blocked on S7-1500 lab session*
- ✅ Unit tests passing — 76 tests green (core, api, plc, storage, codegen, packs, replay, tier, UI client)
- ⏳ Engineer can scan QR → tablet PWA opens single-machine view — *blocked on factory-floor smoke test*

### Why API-first in Phase 1, not Phase 4

Decision recorded as **F-001** (`project_findings_log.md`). Bolting API on later means rewriting `core/` to remove direct UI imports — cheaper to do it right Day 1. The API is the spine; PyQt6 and PWA are both consumers.

---

## 5. Phase 2 — Feature Complete + Machine Packs (Month 3-4)

**Pillar 1: Cycle Analyzer (primary)**
- Real-time cycle streaming (WebSocket fan-out)
- Multi-shift aggregation
- **Cycle Variance metric** (σ between consecutive cycles, per step)
- **Replay Mode**: scrub past 24h with full tag snapshot

**Pillars 2 & 3 MVP:**
- OEE Calculator (A × P × Q)
- Event Logger + downtime taxonomy
- **Operator-as-Sensor** tablet HMI: one-tap downtime reason

**Machine Packs (App Store foundation):**
- Pack manifest schema + `core/pack_loader.py`
- `_template/` ships in repo
- 3 reference packs: CNC 3-axis, bottle filler, robot cell
- YAML→SCL/ST **PLC code generator** scaffold

**API additions:**
- `GET /api/cycles/{id}/replay` — full tag snapshot
- `GET /api/packs` — discovered packs + manifests
- `POST /api/downtime/tag` — operator stoppage reason
- WebSocket: `cycle_anomaly` event when variance > threshold

**Tier gating (mirror ds-vision):**
- Tier profiles: tier_1_machine / tier_5_machines / tier_unlimited
- Recipe (machine config) declares `tier_required`
- Platform refuses to load if license tier insufficient

---

## 6. Phase 3 — Polish & UX (Month 5-6)

**Visual design system (DS-P005-UI-001):**
- Color palette (light + dark mode)
- Component library (cards, buttons, charts) — same source for PyQt6 + PWA
- Icon set (SVG, single source `resources/icons/`)
- Responsive layout (1920×1080 → 1366×768 → tablet → phone)

**UX polish:**
- First-run wizard (commissioning flow)
- Dark mode toggle
- Accessibility (WCAG 2.1 AA — desktop + PWA both audited)
- Keyboard shortcuts (engineer power-user)
- Gantt interactivity (zoom, hover, click-into)
- Error boundary + graceful degradation (PWA shows cached data when API offline)
- **Push notifications** working: alarm/NG → operator's phone

**Documentation:**
- Operator manual (DS-P005-OPR-001) — bilingual EN/VI
- Engineer commissioning guide (DS-P005-COM-001)
- API reference (DS-P005-API-001) — auto-generated from FastAPI OpenAPI
- 3-5 video tutorials (commissioning, operator daily flow, manager dashboard)

---

## 7. Phase 4 — Scale & Cloud (Month 7-8)

**Mode 2 — On-Premise PostgreSQL + TimescaleDB:**
- Multi-machine support (up to 10, all 1 instance)
- TimescaleDB hypertable for cycle data (10× query speed vs. raw Postgres)
- Backup/restore procedures
- Database clustering (read replica for reports)

**Mode 1 — Cloud:**
- Multi-tenant architecture (tenant_id partitioning)
- RBAC enforcement (real JWT, not stub)
- SSO/LDAP integration (optional, customer choice)
- Encryption at-rest + in-transit
- Cloud sync agent: edge-first with optional upload

**Additional protocols:**
- Modbus TCP/RTU (full)
- EtherNet/IP — Allen-Bradley
- ADS — Beckhoff TwinCAT
- MC Protocol — Mitsubishi
- Multi-PLC per machine: 1 logical machine = N physical PLCs (unified clock)

**Scale & monitoring:**
- Load testing (1000 cycles/min × 10 machines)
- Prometheus metrics endpoint
- Grafana dashboards (platform health, not customer data)
- ELK or Loki for log aggregation

---

## 8. Phase 5 — Product Ready (Month 9-12)

**Packaging:**
- PyInstaller .exe (Windows laptop install) — `scripts/build.py`
- Docker image (server install) — Mode 2
- Terraform templates (AWS/Azure) — Mode 1 reference deploy
- Auto-update mechanism (signed manifests)
- First-run wizard polished (deploy < 1 day)

**Advanced features:**
- ML anomaly detection (Cycle Variance baseline → flag outliers)
- SPC charts (X-bar / R / cumulative sum)
- Recipe management (machine config versioning)
- Energy + cycle correlation (Modbus kWh meter)

**Compliance & launch:**
- CE marking (industrial control software classification)
- ISO 9001 audit trail
- GDPR / data residency
- Customer onboarding playbook
- Help desk knowledge base
- 24h first-response SLA tooling

---

## 9. Success Metrics

| Phase | Metric | Target |
|---|---|---|
| 1 | Cycle accuracy vs. PLC timestamp | ≤10 ms |
| 1 | API uptime in lab | 99%+ |
| 1 | OPC-UA reconnect after cable pull | <10 s |
| 1 | Phone PWA install + load | ≤5 s on factory wifi |
| 2 | Cycles processed without error | 1000+ |
| 2 | Cycle Variance detection lead time | ≥2 h before downtime |
| 2 | Pack load time (cold start) | ≤2 s |
| 3 | UX audit | Pass |
| 3 | WCAG 2.1 AA | Pass (desktop + PWA) |
| 3 | Beta NPS | ≥40 (5+ users) |
| 4 | Load test | 1000 cycles/min × 10 machines, 0 data loss |
| 4 | Multi-machine isolation | 1 fault doesn't degrade others |
| 5 | Paying customers | 3+ commercial deployments |
| 5 | Customer NPS | ≥40 |
| 5 | Support SLA | <24 h first-response |

---

## 10. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| OPC-UA edge cases on S7-1500 | Med | High | Real hardware test Week 2-3, no simulator |
| API-first refactor blocks Phase 1 | Med | High | Scaffold day 1, every feature ships through API |
| PWA push notifications blocked by factory IT | Med | Med | Polling fallback, customer-side firewall config doc |
| TimescaleDB ops complexity | Low | Med | Defer to Phase 4, pilot with vanilla Postgres |
| Pack ecosystem fails to take off | Med | Low | Ship 3 reference packs ourselves, community is bonus |
| Customer wants native iOS app | Low | Low | PWA covers 95%, document the architectural reason |
| Multi-PLC clock skew | Med | High | Use NTP/PTP, document min jitter requirement |
| Recipe schema changes break production | High | Critical | Schema versioning + migration logic (Phase 1.2) |
| Team size = 1 (Ha) blocks delivery | High | High | Roadmap stretches; Phase 1-2 prioritize ruthlessly |

---

## 11. Team & Budget

```
Total: 38 person-months over 12 months (full team)
Realistic with team-of-1 + Claude Code: 18-24 months stretched
```

| Phase | Duration | Headcount | Person-Months |
|---|---|---|---|
| 1 | 2 mo | 1-2 | 2-4 |
| 2 | 2 mo | 2-3 | 4-6 |
| 3 | 2 mo | 3-4 | 6-8 |
| 4 | 2 mo | 3-4 | 6-8 |
| 5 | 4 mo | 2-3 | 8-12 |
| **Total** | **12 mo** | **2-4** | **26-38** |

---

## 12. Go/No-Go Gates

| Gate | Trigger | Owner | Date | Status |
|---|---|---|---|---|
| Phase 1 → 2 | Siemens pilot 100 cycles + API live + PWA installs on phone | Ha | ~2026-07-02 | TBD |
| Phase 2 → 3 | All 3 pillars MVP + 3 reference packs + Cycle Variance detection working | Team | ~2026-09-02 | TBD |
| Phase 3 → 4 | UX audit pass + WCAG AA + dark mode + push notifications | Design Lead | ~2026-11-02 | TBD |
| Phase 4 → 5 | Load test pass + multi-PLC working + cloud Mode-1 reference deploy | QA/DevOps | ~2027-01-02 | TBD |
| Phase 5 → Launch | 3+ paying customers + compliance + support SLA | Executive | ~2027-05-02 | TBD |

---

**Document Owner:** Ha (OT Lead)
**Last Updated:** 2026-05-02
**Status:** v1.1 — API-first + PWA + innovations integrated
