# Quick Reference — DS Machine Analyzer Planning Docs

**Status:** ✅ All planning documents created & organized  
**Total Pages:** ~60 (4 core docs + this index)  
**Last Updated:** 2026-05-02

---

## 📂 Document Navigation

### 1. **MASTER_PLAN.md** ← START HERE

**What:** Executive overview of entire project  
**Length:** 8 pages  
**For:** Everyone (developers, managers, stakeholders)  

**Contains:**
- Complete roadmap summary (6 months, 5 phases)
- Team structure & budget
- Success metrics
- Risk mitigation
- Key milestones with weekly breakdowns

**Read if:** You're new to the project and need 5-minute overview

---

### 2. **ROADMAP.md**

**What:** Detailed 6-month development roadmap  
**Length:** 12 pages  
**For:** Product managers, team leads, developers

**Contains:**
- Phase 1-5 detailed breakdown (what, when, who)
- Exit criteria for each phase
- Deliverables checklists
- Budget breakdown (person-months)
- Risk mitigation matrix

**Read if:** You're planning resources or setting sprint goals

---

### 3. **UX_UI_DESIGN_SYSTEM.md**

**What:** Complete design system for professional modern SaaS UI  
**Length:** 15 pages  
**For:** Designers, frontend engineers, visual QA

**Contains:**
- Color palette (light + dark mode)
- Typography hierarchy
- Component library (buttons, cards, tables, etc.)
- Layout architecture
- Responsive breakpoints
- Accessibility guidelines (WCAG 2.1 AA)
- PyQt6 implementation examples

**Read if:** You're building the UI or need design specifications

---

### 4. **INFORMATION_ARCHITECTURE.md**

**What:** User workflows, navigation structure, data organization  
**Length:** 10 pages  
**For:** UX designers, product managers, frontend engineers

**Contains:**
- 4 user personas (engineer, operator, manager, executive)
- Mental models for each role
- Navigation hierarchy (Dashboard → Machines → Cycles → Analytics)
- Task flows (setup wizard, monitoring, analysis)
- Wireframe sketches
- Data filtering rules

**Read if:** You're designing workflows or need to understand user journeys

---

### 5. **RELIABILITY_AVAILABILITY_SCALABILITY.md**

**What:** Non-functional requirements (RAS)  
**Length:** 14 pages  
**For:** Architects, backend engineers, QA, DevOps

**Contains:**
- Zero-data-loss guarantees (transactions, validation)
- Cycle time accuracy requirements (≤10ms)
- Uptime targets (99%+ with auto-recovery)
- Multi-machine scalability (1-10 machines, isolation)
- Database strategies (SQLite laptop → PostgreSQL server)
- Performance targets (response times, throughput)
- Testing plans

**Read if:** You're implementing core features or designing infrastructure

---

## 🎯 Quick Selection Guide

### By Role

**🔧 OT/Backend Engineer (Ha)**
→ Read in order: MASTER_PLAN → ROADMAP → RELIABILITY_AVAILABILITY_SCALABILITY → Code

**🎨 UI/Frontend Engineer**
→ Read in order: MASTER_PLAN → INFORMATION_ARCHITECTURE → UX_UI_DESIGN_SYSTEM → Code

**👁️ UX/Product Designer**
→ Read in order: MASTER_PLAN → INFORMATION_ARCHITECTURE → UX_UI_DESIGN_SYSTEM

**⚙️ DevOps/Infrastructure**
→ Read in order: MASTER_PLAN → ROADMAP → RELIABILITY_AVAILABILITY_SCALABILITY

**✅ QA/Test**
→ Read in order: MASTER_PLAN → RELIABILITY_AVAILABILITY_SCALABILITY → INFORMATION_ARCHITECTURE (test user flows)

**📊 Product Manager/Executive**
→ Read in order: MASTER_PLAN → ROADMAP → (Optional: RELIABILITY_AVAILABILITY_SCALABILITY)

---

### By Question

**❓ "When do we ship?"**  
→ ROADMAP.md — see Phase 5 timeline (~May 2027)

**❓ "What does the UI look like?"**  
→ UX_UI_DESIGN_SYSTEM.md — color palette, components, layouts

**❓ "How do users interact?"**  
→ INFORMATION_ARCHITECTURE.md — personas, task flows, wireframes

**❓ "How do we avoid data loss?"**  
→ RELIABILITY_AVAILABILITY_SCALABILITY.md — transactions, validation

**❓ "Can 10 machines run simultaneously?"**  
→ RELIABILITY_AVAILABILITY_SCALABILITY.md → Scalability section

**❓ "What's the team structure?"**  
→ MASTER_PLAN.md — Team Structure section

**❓ "What are success metrics?"**  
→ ROADMAP.md + MASTER_PLAN.md — Success Metrics by Phase

**❓ "How much budget do we need?"**  
→ ROADMAP.md or MASTER_PLAN.md — Budget Estimate section

---

## 📋 Phase Checklist Template

### Phase 1: Safety & Foundation

**Prepare (Week 0):**
- [ ] Team on same page (read MASTER_PLAN + ROADMAP)
- [ ] Development environment setup
- [ ] Project structure created ✅ (already done)

**Do (Week 1-8):**
- [ ] OPC-UA handshake protocol (real S7-1500)
- [ ] SQLite database schema
- [ ] Cycle Processor engine
- [ ] Basic PyQt6 UI
- [ ] Unit tests

**Validate (Week 9):**
- [ ] Review vs. RELIABILITY_AVAILABILITY_SCALABILITY.md RAS requirements
- [ ] Phase 1 → 2 go/no-go gate
- [ ] Lessons learned documented

---

## 🚀 One-Pager Summary

```
PROJECT:   DS Machine Analyzer Platform
TIMELINE:  6 months (May 2026 - May 2027)
TEAM:      3-4 core + specialists
BUDGET:    ~$3M (full team) or $1.2-1.6M (2-person core)
SCOPE:     3 pillars, 4 user roles, 3 deployment modes
GOAL:      Professional PLC analytics for manufacturing

PHASES:
  1 (M1-2):  Safety & Foundation (OPC-UA pilot + SQLite)
  2 (M3-4):  Feature Complete (all 3 pillars MVP)
  3 (M5-6):  Polish & UX (dark mode, accessibility)
  4 (M7-8):  Scale & Cloud (PostgreSQL, multi-machine)
  5 (M9-12): Product Ready (packaging, compliance, launch)

METRICS:
  • Cycle accuracy: ≤10ms
  • Uptime: 99%+
  • Data loss: 0 events
  • Customer NPS: ≥40
  • Paying customers: 3+
```

---

## 📖 Document Cross-References

If you're reading MASTER_PLAN:
→ Deep dive: ROADMAP, UX_UI_DESIGN_SYSTEM, INFORMATION_ARCHITECTURE, RELIABILITY_AVAILABILITY_SCALABILITY

If you're reading ROADMAP:
→ Related: Phase 3 design system in UX_UI_DESIGN_SYSTEM
→ Related: RAS requirements in RELIABILITY_AVAILABILITY_SCALABILITY

If you're reading UX_UI_DESIGN_SYSTEM:
→ Related: User journeys in INFORMATION_ARCHITECTURE
→ Related: Timeline for implementation in ROADMAP Phase 3

If you're reading INFORMATION_ARCHITECTURE:
→ Related: Visual design in UX_UI_DESIGN_SYSTEM
→ Related: Timeline in ROADMAP

If you're reading RELIABILITY_AVAILABILITY_SCALABILITY:
→ Related: Phases in ROADMAP (testing happens each phase)
→ Related: User scenarios in INFORMATION_ARCHITECTURE

---

## ✏️ How to Update Docs

### If You Find an Error
1. Note the doc name + page
2. Report to Ha or product lead
3. Fix in docs/ folder
4. Update "Last Updated" dates
5. Commit with message: "docs: Fix [section] in [document]"

### If Requirements Change
1. Update the specific doc section
2. Check if other docs need updating (cross-references)
3. Add entry to "Document Versioning" table
4. Notify team in sync meeting

### If You Add a New Phase/Feature
1. Update ROADMAP.md (add to timeline)
2. Update MASTER_PLAN.md (adjust go/no-go gates)
3. Update IA docs (new workflows)
4. Update RAS docs (new test cases)

---

## 🎓 Learning Path (1 Hour Introduction)

**New team member onboarding:**

1. **MASTER_PLAN.md** (15 min readtime)
   - Overview of project
   - Meet the team
   - Understand phases

2. **ROADMAP.md** (Phase 1-2 sections only, 10 min readtime)
   - What we do in first 4 months
   - What's expected

3. **Your Role-Specific Doc** (20 min readtime)
   - If backend: RELIABILITY_AVAILABILITY_SCALABILITY
   - If frontend: UX_UI_DESIGN_SYSTEM + INFORMATION_ARCHITECTURE
   - If designer: INFORMATION_ARCHITECTURE + UX_UI_DESIGN_SYSTEM

4. **Q&A + Code Tour** (15 min)
   - Walk through project structure
   - Run first test
   - Answer questions

---

## 🔗 Related Resources

**In Project Folder:**
- `/docs/CLAUDE.md` — Architecture context for Claude Code CLI
- `/README.md` — Technical quick-start

**In Code:**
- `/core/` — Pure Python engine (reference RELIABILITY_AVAILABILITY_SCALABILITY)
- `/ui/` — PyQt6 interface (reference UX_UI_DESIGN_SYSTEM)
- `/tests/` — Test suite (reference RELIABILITY_AVAILABILITY_SCALABILITY test plans)

**External References:**
- `/c/dev/Projects/ds-vision/` — Similar project (reference architecture)
- OPC Foundation specs — For protocol details
- WCAG 2.1 guidelines — For accessibility

---

## ⚡ TL;DR for Busy People

**What:** Professional PLC analytics software  
**Timeline:** 6 months  
**Team:** 3-4 people  
**Budget:** $1.2M-3M  
**Goal:** Ship with 3+ paying customers by May 2027  
**First Phase:** Reliable OPC-UA integration + SQLite DB (2 months)  
**Success Metric:** 99%+ uptime, ≤10ms cycle time accuracy, zero data loss

---

## 📞 Contacts

| Role | Name | Responsibility |
|------|------|-----------------|
| OT/Product Lead | Ha | Architecture, roadmap, PLC integration |
| UX/Design Lead | [TBD] | All design decisions |
| Backend Lead | Ha or hire | Core engine, database |
| DevOps Lead | [TBD] | Infrastructure, CI/CD |

💡 **Tip:** If you have a question not answered by these docs, ask in the weekly sync or create an ADR (Architecture Decision Record) in `docs/ADR/`

---

**Version:** 1.0-Beta  
**Last Updated:** 2026-05-02  
**Maintained By:** Ha (OT Lead)  

🚀 **Ready to build something great!**
