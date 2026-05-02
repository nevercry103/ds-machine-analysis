# DS Machine Analyzer Platform — Master Planning Guide

**Created:** 2026-05-02  
**Status:** Phase 1 (Safety & Foundation) — Active  
**Ownership:** Ha (OT/Product Lead), UX/Design Lead, DevOps Lead

---

## 📋 Overview

DS Machine Analyzer is a **6-month product development initiative** to build a professional, user-friendly industrial machine analytics platform for manufacturing.

**Three Pillars (Features):**
1. **Cycle Analyzer** (Pilot) — Step timing, bottleneck detection
2. **OEE Analyzer** (Planned) — Availability × Performance × Quality
3. **Event Logger** (Planned) — PLC alarms, downtime tracking

**Three Deployment Modes (Same Code):**
1. **DS Cloud** — Multi-tenant SaaS
2. **On-Premise Server** — Dedicated customer installation
3. **Laptop Mode** — Commission, engineering, testing

**Four User Roles (Different Views):**
1. **OT Engineer** — Setup, diagnostics, commissioning
2. **Plant Operator** — Daily shift monitoring, alerts
3. **Manufacturing Manager** — Reporting, bottleneck analysis, KPIs
4. **Factory Executive** — High-level OEE dashboard

---

## 📚 Documentation Structure

All planning documents live in `docs/` folder:

```
docs/
├── ROADMAP.md (THIS FILE)
│   └── 6-month phased development plan
│       • Phase 1-5 breakdown
│       • Success metrics & dependencies
│       • Team & budget allocation
│
├── UX_UI_DESIGN_SYSTEM.md
│   └── Professional SaaS design system
│       • Color palette (light + dark)
│       • Component library
│       • Layout architecture
│       • Accessibility (WCAG 2.1 AA)
│
├── INFORMATION_ARCHITECTURE.md
│   └── User workflows & data organization
│       • 4 user personas & mental models
│       • Navigation structure
│       • Task flows & wireframes
│
├── RELIABILITY_AVAILABILITY_SCALABILITY.md
│   └── Technical RAS requirements
│       • Zero-data-loss guarantees
│       • Auto-recovery mechanisms
│       • Multi-machine scalability (1-10)
│       • Database strategies (SQLite → PostgreSQL)
│
└── README.md
    └── Technical quick-start for developers
```

---

## 🎯 Phase Overview

### Phase 1: Safety & Foundation (Month 1-2) 🚧 ACTIVE

**Goal:** Establish reliable architecture, pilot OPC-UA + S7-1500

**Key Deliverables:**
- ✅ Project structure (done)
- ⏳ OPC-UA handshake protocol (with real S7-1500)
- ⏳ SQLite database schema
- ⏳ Cycle Processor engine (step stats, bottleneck)
- ⏳ Basic PyQt6 UI skeleton

**Exit Criteria:**
- Zero data loss over 100 test cycles
- Cycle time accuracy ≤10ms
- OPC-UA connection stable (99%+ uptime in lab testing)
- Unit tests passing (core layer)

---

### Phase 2: Feature Complete (Month 3-4)

**Goal:** 3 pillars MVP, integration tested, first pilot candidate

**Key Deliverables:**
- OEE Analyzer (MVP: availability, performance, quality metrics)
- Event Logger (MVP: PLC alarm capturing)
- UI: Cycle history, analytics tables, export
- Configuration: YAML machine config loader

**Exit Criteria:**
- All 3 pillars functional (even if simple)
- 1000+ cycles processed without error
- First customer pilot deployment checklist ready

---

### Phase 3: Polish & UX (Month 5-6)

**Goal:** Production-ready UI/UX, dark mode, accessibility

**Key Deliverables:**
- Design system finalized (Figma file)
- Dark mode implementation
- Accessibility audit (WCAG 2.1 AA pass)
- First-run wizard (optimized)
- User documentation (manual, FAQ, videos)

**Exit Criteria:**
- UX audit pass (design review)
- Keyboard navigation complete
- 3+ beta users test & provide feedback

---

### Phase 4: Scale & Cloud (Month 7-8)

**Goal:** Multi-machine support, PostgreSQL, cloud-ready

**Key Deliverables:**
- PostgreSQL (Mode 2) deployment
- Multi-tenant architecture (Mode 1 prep)
- Load testing (1000 cycles/min, 10 machines)
- Monitoring stack (Prometheus + Grafana)
- Additional protocols (Modbus, EtherNet/IP)

**Exit Criteria:**
- Load test pass (no data loss, <100ms query time)
- Multi-machine isolation verified
- Database auto-archival strategy proven

---

### Phase 5: Product Ready (Month 9-12)

**Goal:** Launch-ready, packaged, supported

**Key Deliverables:**
- PyInstaller .exe (Windows) + Docker (server)
- Customer onboarding playbook
- Help desk knowledge base
- Advanced features: ML anomaly detection, SPC charts
- Compliance documentation (CE, ISO 9001)

**Exit Criteria:**
- 3+ paying customers (pilot or commercial)
- NPS ≥40
- <24h first-response support SLA

---

## 🏗️ Architecture at a Glance

```
┌─ FRONTEND (PyQt6 Desktop) ──────────────────┐
│  4 Role-based Dashboards                    │
│  • Engineer: Diagnostics focus              │
│  • Operator: Real-time cycle monitoring     │
│  • Manager: Bottleneck analysis             │
│  • Executive: OEE high-level only           │
├─ BACKEND (Pure Python, Async) ─────────────┤
│  Machine Registry (1-10 machines)           │
│  Data Bus (event stream)                    │
│  Cycle Processor (Pillar 1)                 │
│  OEE Processor (Pillar 2 stub)              │
│  Event Logger (Pillar 3 stub)               │
├─ PROTOCOL LAYER (Abstract Adapters) ───────┤
│  • OPC-UA (Siemens S7-1500 pilot)           │
│  • Modbus TCP/RTU (planning)                │
│  • EtherNet/IP (planning)                   │
│  All inherit BaseProtocolAdapter            │
├─ STORAGE LAYER (Dual Backend) ─────────────┤
│  • SQLite (Mode 3: laptop)                  │
│  • PostgreSQL (Mode 1 & 2: server/cloud)    │
│  Same async interface, different impl       │
└─────────────────────────────────────────────┘
```

---

## 📊 Success Metrics by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| **1** | Cycle accuracy | ≤10ms error vs. PLC |
| | Data loss | 0 events |
| | OPC-UA uptime (lab) | 99%+ |
| **2** | All pillars ready | MVP + stubs functional |
| | Cycles processed | 1000+ error-free |
| | First pilot | Deployment checklist ready |
| **3** | UX audit | Pass |
| | Accessibility | WCAG 2.1 AA |
| | Beta test feedback | 5+ users, NPS ≥40 |
| **4** | Load testing | 1000 cycles/min, 10 machines |
| | Database scale | <500ms query on 1M rows |
| | Multi-machine isolation | 1 failure doesn't affect others |
| **5** | Paying customers | 3+ commercial deployments |
| | Support SLA | <24h first-response |
| | Customer NPS | ≥40 |

---

## 👥 Team Structure

### Core Team (Minimum)

| Role | Responsibility | Person |
|------|-----------------|--------|
| OT/Product Lead | Architecture, PLC integration, roadmap | Ha |
| Backend Engineer | Core engine, database, protocol adapters | Ha or hire |
| Frontend/UX Engineer | PyQt6 UI, design system, UX | Hire ~Phase 2 |
| DevOps/Infrastructure | Docker, CI/CD, monitoring, deployment | Shared resource |
| QA/Test | Automation, hardware testing, pilot management | Hire ~Phase 3 |

### Recommended Additions

| Phase | Role | Reason |
|-------|------|--------|
| 1-2 | OT Protocol Specialist | Speed up Modbus/EtherNet/IP adapters |
| 3 | UX Designer (contractor) | Design system, accessibility audit |
| 4 | Cloud Architect | AWS/Azure setup, K8s |

---

## 💰 Budget & Resource Allocation

```
Total Project: 38 person-months over 12 months

Breakdown:
  Phase 1 (2mo):   4 PM  (2 people × 2 months)
  Phase 2 (2mo):   6 PM  (3 people × 2 months)
  Phase 3 (2mo):   8 PM  (4 people × 2 months)
  Phase 4 (2mo):   8 PM  (4 people × 2 months)
  Phase 5 (4mo):  12 PM  (3 people × 4 months)
                  ─────
  Total:          38 PM

At $80K/person-month (loaded):
  Estimated: $3.04M (full team)
  
If team of 2 (Ha + 1 other):
  Stretched timeline: 18-24 months
  Cost: ~$1.2-1.6M
```

---

## 🎬 Get Started Checklist (Week 1)

- [ ] **Ha:** Review all 4 docs (ROADMAP, UX/UI, IA, RAS)
- [ ] **Ha:** Verify project folder structure is correct
- [ ] **Ha:** Set up development environment (Python 3.11, PyQt6, asyncua)
- [ ] **Ha:** Schedule PLC access (S7-1500 hardware for OPC-UA testing)
- [ ] **Team:** First sprint planning (Phase 1 tasks)
- [ ] **Team:** Set up CI/CD (GitHub Actions or similar)
- [ ] **Team:** Create design review schedule (weekly)

---

## 🚀 Key Upcoming Milestones

### Month 1-2 (Phase 1)

```
Week 1:   Development environment setup, OPC-UA driver testing
Week 2-3: Siemens OPC-UA handshake protocol (real hardware)
Week 4:   SQLite database schema, Cycle Processor engine
Week 5-6: PyQt6 basic UI, end-to-end test (PLC → DB → UI)
Week 7-8: Performance testing (100 cycles), unit test suite
Week 9:   Architecture review, Phase 1 exit decision
```

### Month 3-4 (Phase 2)

```
Week 10-11: UI development (analytics, tables, export)
Week 12-13: OEE Processor MVP, Event Logger MVP
Week 14-15: Integration testing (all 3 pillars)
Week 16:    First pilot deployment preparation
```

### Month 5-6 (Phase 3)

```
Design system finalization
Dark mode implementation
Accessibility audit & fixes
User documentation
Beta testing with 3-5 users
```

---

## 🔒 Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| OPC-UA issues with S7-1500 | HIGH | Early real hardware testing (Week 2-3) |
| PostgreSQL performance | HIGH | Load testing by end of Phase 3 |
| Multi-machine race conditions | HIGH | Integration tests each phase |
| Customer data loss | CRITICAL | Transaction logging, automated backup |
| Scope creep (extra features) | MEDIUM | Strict Phase gates, backlog discipline |
| Team attrition | HIGH | Clear roadmap, mentorship program |

---

## 📖 How to Use This Guide

### For Developers

1. **Start here:** [ROADMAP.md](ROADMAP.md) — Understand what we're building & timeline
2. **Then read:** [INFORMATION_ARCHITECTURE.md](INFORMATION_ARCHITECTURE.md) — How users interact
3. **Finally:** [UX_UI_DESIGN_SYSTEM.md](UX_UI_DESIGN_SYSTEM.md) — What it looks like
4. **Reference:** [RELIABILITY_AVAILABILITY_SCALABILITY.md](RELIABILITY_AVAILABILITY_SCALABILITY.md) — Non-functional requirements

### For Design/UX

1. **Start here:** [UX_UI_DESIGN_SYSTEM.md](UX_UI_DESIGN_SYSTEM.md) — Complete design system
2. **Reference:** [INFORMATION_ARCHITECTURE.md](INFORMATION_ARCHITECTURE.md) — User mental models
3. **Coordinate with:** [ROADMAP.md](ROADMAP.md) — Phase 3 timeline for UX design

### For Product/Management

1. **Start here:** [ROADMAP.md](ROADMAP.md) — Phases, timelines, metrics
2. **Deep dive:** [RELIABILITY_AVAILABILITY_SCALABILITY.md](RELIABILITY_AVAILABILITY_SCALABILITY.md) — Technical commitments
3. **Reference:** All other docs for stakeholder communication

### For QA/Test

1. **Start here:** [RELIABILITY_AVAILABILITY_SCALABILITY.md](RELIABILITY_AVAILABILITY_SCALABILITY.md) — Test plans
2. **Reference:** [INFORMATION_ARCHITECTURE.md](INFORMATION_ARCHITECTURE.md) — User flows to test
3. **Coordinate:** [ROADMAP.md](ROADMAP.md) — Which phase needs which tests

---

## 📞 Communication & Feedback

**Weekly Syncs:**
- Monday 10am: Technical standup (15min)
- Wednesday 2pm: Design review (30min)
- Friday 4pm: Phase checkpoint (30min)

**Documentation:**
- Update these docs at phase transitions
- Use Git commit messages referencing doc sections
- Monthly: Roadmap health check (on track?)

**Decision Record:**
- Major decisions documented in ADR (Architecture Decision Record)
- Stored in `docs/ADR/` folder

---

## 🎓 Knowledge Resources

**DS Vision Platform (Reference):**
- Folder structure: `/c/dev/Projects/ds-vision/`
- Similar PyQt6 + async patterns
- Multi-device support inspiration (ds-vision has 5+ camera brands; we have 6+ protocols)

**Open Standards:**
- IEC 61131-3 (PLC languages)
- OPC Unified Architecture spec (https://opcfoundation.org/)
- WCAG 2.1 (Accessibility)

---

## ✅ Appendix: Go/No-Go Gates

| Gate | Trigger | Owner | Date | Y/N |
|------|---------|-------|------|-----|
| Phase 1 → 2 | Siemens pilot successful (real HW, 100 cycles) | Ha | ~Jun 2 | TBD |
| Phase 2 → 3 | All 3 pillars MVP, zero data loss confirmed | Team | ~Aug 2 | TBD |
| Phase 3 → 4 | UX audit pass, dark mode ready, beta feedback | Design Lead | ~Oct 2 | TBD |
| Phase 4 → 5 | Load test pass (1000 cycles/min) | QA/DevOps | ~Dec 2 | TBD |
| Phase 5 → Launch | Product ready, first customer signed | Executive | ~May 2027 | TBD |

---

## 📝 Document Versioning

| Version | Date | Changes |
|---------|------|---------|
| 1.0-Beta | 2026-05-02 | Initial comprehensive planning (ROADMAP, UX/UI, IA, RAS) |
| — | — | — |

---

**Next Review:** End of Phase 1 (expected ~June 2026)

**Questions?** Reach out to Ha (OT Lead) or refer to specific docs.

---

**This is your blueprint for building DS Machine Analyzer. Follow it, measure against it, update it as you learn. Good luck! 🚀**
