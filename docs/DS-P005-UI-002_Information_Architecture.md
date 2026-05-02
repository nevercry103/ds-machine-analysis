# Information Architecture — DS Machine Analyzer

**Scope:** User workflows, data organization, mental models for 4 user roles

---

## 1. User Personas & Tasks

### Persona 1: OT Engineer (Ha)
**Goal:** Setup PLC connections, verify data integrity, troubleshoot  
**Primary Task:** Diagnose why PLC isn't connecting  
**Entry Point:** Dashboard → Diagnostics

### Persona 2: Plant Operator  
**Goal:** Monitor cycles, spot issues, alert manager  
**Primary Task:** Watch current cycle progress in real-time  
**Entry Point:** Dashboard (main view)

### Persona 3: Manufacturing Manager  
**Goal:** Understand shift performance, identify bottlenecks, report  
**Primary Task:** Which step is slowest? Is it degrading?  
**Entry Point:** Dashboard → Analytics → Bottleneck

### Persona 4: Factory Executive  
**Goal:** Understand OEE, make ROI decisions  
**Primary Task:** What's our OEE score this week?  
**Entry Point:** Dashboard (KPI view only)

---

## 2. Information Architecture

### Top-Level Navigation

```
DASHBOARD (Home)
├── Real-time Monitor
│   ├── Connection Status
│   ├── Current Cycle Progress
│   ├── Step Breakdown
│   └── Alerts
│
├── KPI Summary (role-dependent)
│   • Engineer: Last 10 cycles
│   • Operator: This shift summary
│   • Manager: OEE + Bottleneck
│   • Executive: OEE only
│
└── Quick Actions (role-dependent)
    • Engineer: [Test Connection] [Configure]
    • Operator: [Export]
    • Manager: [View Reports]

MACHINES (Management)
├── Machine List
│   • Connection status
│   • Last cycle time
│   • Actions: [Edit] [Test] [Delete]
│
└── Add New Machine (Wizard)
    ├── Step 1: Basic Info
    ├── Step 2: Protocol Selection
    ├── Step 3: Connection Details
    ├── Step 4: Step Configuration
    └── Step 5: Confirm

CYCLES (History)
├── Cycle List (Searchable, Filterable)
│   • Today / This Week / This Month
│   • Sort by: Time, Duration, Status
│
├── Cycle Detail
│   • Metadata: ID, Time, Duration
│   • Step Breakdown (table + Gantt)
│   • Alerts & anomalies
│   • Export: CSV, Excel, JSON
│
└── Batch Actions: Export Multiple, Compare

ANALYTICS
├── Bottleneck Analysis
│   • Step ranking by avg time
│   • Drill down to cycle level
│
├── Trends
│   • Cycle time trend (7/30/90 days)
│   • Step time trends
│   • Distribution analysis
│
├── OEE Dashboard (Pillar 2)
│   • Availability, Performance, Quality
│   • Combined OEE score
│
└── Reports
    • Shift Report (PDF)
    • Daily Report (Excel)
    • Custom Report Builder

DIAGNOSTICS (Engineer)
├── Connection Test
│   • Test PLC → Show latency
│   • Timestamp sync check
│   • Handshake validation
│
├── Data Integrity Check
│   • Last 10 cycles validity
│   • Step count validation
│
├── Performance Monitor
│   • CPU, Memory, DB query time
│
└── Logs
    • Last 100 error entries
    • Debug mode toggle

SETTINGS
├── General
├── Appearance (Light/Dark)
├── Notifications (Thresholds)
├── Data (Backup/Restore)
├── Account (Role switching)
└── About
```

---

## 3. Data Organization & Filtering

### Cycle History Filters

```
Primary: Time Range [Today ▼]
Secondary: Machine, Status, Duration
Search: By Cycle ID or Time
Sort: Cycle #, Time, Duration
Pagination: Show 50 rows per page
```

### Step Statistics Sorting

```
Default: Sort by Avg Time (descending)
Bottleneck highlighted: ● Execute 1.2s

Click → Drill down to individual cycles
```

---

## 4. Key Task Flows

### Flow 1: First-Time Setup (Engineer)

```
1. Welcome → Get Started
2. Machine Info → Enter ID, name
3. Protocol → Select OPC-UA
4. Connection → Enter IP:port, test
5. Steps → Add production steps
6. Success → Dashboard (live data)
```

### Flow 2: Monitor Cycle (Operator)

```
1. Dashboard → Live progress display
2. Watch cycle in real-time
3. Alert: If slow, toast notification
4. Complete: Auto-show in history
5. Export: [Export] button on dashboard
```

### Flow 3: Analyze Bottleneck (Manager)

```
1. Analytics → Bottleneck Analysis
2. See ranking: Sort by avg time
3. Click "Execute" → Drill down
4. See trend: Chart of last 24h
5. View cycles: Near-slowest ones
6. Root cause: Suggestion or drill deeper
```

### Flow 4: Report (Manager)

```
1. Reports → Custom Report Builder
2. Date range, machines, sections
3. Format: PDF / Excel
4. [Generate] → Download
5. [Share] / [Save as template]
```

---

## 5. Content Hierarchy by Role

### Engineer View

```
1. Connection diagnostics (top priority)
2. Real-time cycle breakdown
3. Raw data access
4. Configuration editing
```

### Operator View

```
1. Large cycle progress (top priority)
2. Current step info (time, status)
3. Last 10 cycles summary
4. Simple export
```

### Manager View

```
1. OEE metrics (top priority)
2. Bottleneck identification
3. Shift-to-shift comparison
4. Export/reporting
```

### Executive View

```
1. OEE score only (top priority)
2. Trend arrow (up/down)
3. Link to details (optional)
```

---

## 6. Wireframe Sketches

### Dashboard Layout (Engineer)

```
┌─────────────────────────────────────────────┐
│ DS Analyzer    [Search] [?] [Settings]      │
├────────┬──────────────────────────────────────┤
│        │ Connection: OPC-UA ✓                │
│ Side   │ IP: 192.168.1.10 | Latency: 12ms   │
│ bar    │                                     │
│        │ Cycle #1248                         │
│        │ ▓▓▓▓░░░░░░░░ 35%                   │
│        │ Step 2: Setup (0.1s / 0.8s)        │
│        │                                     │
│        │ [Details] [Pause] [Reset]          │
│        │                                     │
│        │ Recent Cycles:                      │
│        │ # | Start    | Duration | Status   │
│        │ 1248 | 14:32 | 2.34s   | ✓       │
│        │ 1247 | 14:31 | 2.15s   | ✓       │
│        │ 1246 | 14:29 | 2.45s   | ⚠       │
│        │                                     │
└────────┴──────────────────────────────────────┘
```

### Bottleneck Analysis (Manager)

```
┌─────────────────────────────────────────────┐
│ Analytics → Bottleneck Analysis             │
├─────────────────────────────────────────────┤
│ Step Ranking:                               │
│ Execute  │ 1.2s  │ 1248 | ↑ 0.1s │ 🔴      │
│ Setup    │ 0.9s  │ 1248 | ↓     │         │
│ Quality  │ 0.8s  │ 1248 | →     │         │
│                                             │
│ Trend Chart (Execute):                      │
│ [Line chart: last 24h]                      │
│                                             │
│ Suggestion:                                 │
│ "Degradation detected. This step was 0.2s  │
│  faster this morning. Check equipment."    │
│                                             │
│ [View Recent Cycles] [Details]             │
└─────────────────────────────────────────────┘
```

---

## 7. Navigation Patterns

### Breadcrumbs

```
[Dashboard] > [Analytics] > [Bottleneck] > [Execute]

Click back (or breadcrumb) → Return to last filtered Bottleneck view
```

### State Preservation

```
Store:
  • Filter state (date range, machine)
  • Drill-down level (Execute step detail)
  • Scroll position

On back: Restore exact view + state
```

---

## 8. Entry Points by Task

| Task | Persona | Entry Point | Click Path |
|------|---------|-------------|-----------|
| Setup machine | Engineer | Dashboard | [Machines] → [Add Machine] |
| Monitor cycle | Operator | Dashboard | (default view) |
| Find bottleneck | Manager | Dashboard | [Analytics] → [Bottleneck] |
| View OEE | Executive | Dashboard | (KPI banner only) |
| Check errors | Engineer | Dashboard | [Diagnostics] → [Logs] |
| Export data | Manager | Cycles | [Cycles] → [Select] → [Export] |

---

## 9. Consistency Patterns

### All Card Layouts

```
┌─────────────────────┐
│ Title               │ Gray header
├─────────────────────┤
│ [Content area]      │ White body
│                     │
│ [Optional: Footer]  │ Gray footer
└─────────────────────┘
```

### All Modal/Dialog Layouts

```
┌─────────────────────────────┐
│ Title                   [X] │
├─────────────────────────────┤
│ [Form/Content]              │
│                             │
├─────────────────────────────┤
│              [Cancel] [OK]  │
└─────────────────────────────┘
```

---

**Document Owner:** Ha (OT Lead) + UX Designer  
**Last Updated:** 2026-05-02  
**Version:** 1.0-Beta
