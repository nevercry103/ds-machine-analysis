# DS Machine Analyzer — UX/UI Design System

**Scope:** Professional, user-friendly interface following modern SaaS principles.

**Framework:** PyQt6 (desktop), responsive design (1280x720 minimum)

**Theme:** Light (primary) + Dark mode option

---

## 1. Visual Design System

### Color Palette — Light Theme

```
Primary (Action):
  Brand Blue: #2563EB
  Hover: #1D4ED8
  Active: #1E40AF

Semantic:
  Success (Green): #059669
  Warning (Yellow): #D97706
  Error (Red): #DC2626
  Info (Cyan): #0891B2
  Bottleneck (Orange): #EA580C

Neutral:
  Text Primary: #111827
  Text Secondary: #6B7280
  Border: #E5E7EB
  Background: #F9FAFB
  Card Background: #FFFFFF
```

### Color Palette — Dark Theme

```
Background: #0F172A
Card Background: #1E293B
Text Primary: #F1F5F9
Text Secondary: #94A3B8
Border: #334155
Primary: #60A5FA
```

### Typography

```
Font Family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
Monospace: "Cascadia Code", Courier New

Sizes:
  H1: 32px, 700
  H2: 24px, 700
  H3: 18px, 600
  Body: 14px, 400
  Small: 12px, 400
```

### Spacing Scale

```
Base Unit: 4px

xs: 4px | sm: 8px | md: 12px | lg: 16px
xl: 24px | 2xl: 32px | 3xl: 48px
```

### Shadows & Borders

```
Border Radius:
  sm: 4px | md: 8px | lg: 12px

Shadows:
  sm: 0 1px 2px rgba(0,0,0,0.05)
  md: 0 4px 6px rgba(0,0,0,0.1)
  lg: 0 10px 15px rgba(0,0,0,0.1)
```

---

## 2. Component Library

### Buttons

```
Primary Button:
  Background: #2563EB (blue)
  Padding: 12px horizontal, 12px vertical
  Border-radius: 8px
  Hover: #1D4ED8
  
Secondary Button:
  Border: 1px #E5E7EB
  Background: transparent
  
Danger Button:
  Background: #DC2626 (red)
```

### Status Indicators

```
Connected:  ● PLC Connected (green pill)
Connecting: ⟳ Connecting... (yellow)
Error:      ⚠ Connection Lost (red)
```

### Real-Time Cycle Display

```
Current Cycle Progress:
  ▓▓▓▓▓░░░░░░░░░░░░░░  35% progress bar
  Step 2: Setup (0.1s / 0.8s)
  
Step Breakdown Table:
  Step | Status  | Name    | Duration
  1    | ✓ Done  | Loading | 1.2s
  2    | ▶ Active| Setup   | 0.1s
  3    | ○ Wait  | Execute | —
```

### Alert/Toast Notifications

```
Success: ✓ Cycle data exported (green, 4s auto-dismiss)
Warning: ⚠ Cycle time 2.3s exceeds target (yellow, manual dismiss)
Error: ✗ PLC Connection Lost [RECONNECT] (red, action required)
```

### Data Tables

```
Cycle # | Start Time  | Duration | Status | Actions
1248    | 14:32:05    | 2.34s    | ✓ OK   | • • •
1247    | 14:31:02    | 2.15s    | ✓ OK   | • • •
(striped rows, hover highlight)
```

---

## 3. Layouts

### Main Application Layout

```
┌─────────────────────────────────────────────┐
│ DS Analyzer        [Search] [Settings] [?] │ Header (56px)
├──────────┬──────────────────────────────────┤
│          │                                  │
│ Sidebar  │     Main Content Area            │
│ (240px)  │   (responsive, flex)             │
│          │                                  │
│ • Dash   │  ┌────────────────────────────┐ │
│ • Mach   │  │ Dashboard / Tab Content   │ │
│ • Cycle  │  │                             │ │
│ • Analy  │  │                             │ │
│ • Setng  │  └────────────────────────────┘ │
│          │                                  │
└──────────┴──────────────────────────────────┘

Responsive: Sidebar collapses at ≤1366px
```

### Dashboard Layouts by Role

#### Engineer (Commissioning Focus)

```
Machine Selector: [Select Machine ▼]
Connection Status: IP, Namespace, Latency
Cycle Progress: Current cycle real-time
Step Breakdown: Live table
Diagnostics: [Test Connection] [View Config]
```

#### Operator (Daily Monitoring)

```
Large Cycle Display: ▓▓▓░░░  Status + Time
Current Step: Highlighted, time estimate
Last 10 Cycles: Summary table
Alerts: Any anomalies
Actions: [Pause] [Reset] [Export]
```

#### Manager (Reporting)

```
KPI Banner: OEE, Avg Time, Best, Total Cycles
Shift Comparison: Chart showing trend
Bottleneck: Which step is slow?
Actions: [Export PDF] [Email] [Archive]
```

#### Executive (30-second Overview)

```
OEE: Large metric display (87.3% ✓)
Availability, Performance, Quality: Three sub-metrics
Trend: ↑ Improving or ↓ Declining
Status: All normal (green banner)
```

---

## 4. Navigation & IA

### Global Navigation

```
Dashboard → Machines → Cycles → Analytics → Settings → Help
```

### Sidebar Menu (Collapsed on Laptop)

```
MAIN
  Dashboard
  Real-Time Monitor

MANAGEMENT
  Machines
  Configuration

ANALYTICS
  Cycles
  Bottleneck Analysis
  Reports

OPERATIONS
  Alerts
  Diagnostics

SETTINGS
  General
  Appearance
  Notifications
  Data
  Account
  About
```

---

## 5. Responsive Breakpoints

```
Desktop XL: ≥1920px (primary)
Desktop:    1280-1919px
Laptop:     1024-1279px (sidebar collapses)
Tablet:     768-1023px (future)
Mobile:     <768px (not supported yet)
```

---

## 6. Accessibility (WCAG 2.1 AA)

### Keyboard Navigation

```
Tab Order: Natural (left→right, top→bottom)
Focus Indicator: 2px blue outline
Shortcuts:
  Ctrl+N → New
  Ctrl+E → Export
  Ctrl+S → Save
  Ctrl+, → Settings
  Esc → Close/Clear
```

### Color Contrast

```
Normal text: 4.5:1 (dark on light)
Large text: 3:1
Example:
  • #111827 on white: 21:1 ✓
  • #2563EB on white: 5.2:1 ✓
  • #DC2626 on white: 5.3:1 ✓
```

### Screen Reader

```
Semantic HTML: <button>, <label>, <nav>, <main>
ARIA:
  • Live regions: aria-live="polite"
  • Alerts: role="alert"
  • Modals: role="dialog"
  • Icon-only buttons: aria-label="Export"
```

---

## 7. Dark Mode

### Activation

```
Settings → Appearance → [Light] [Dark] [System Default]
Persisted in localStorage
```

### Dark Palette

```
Background: #0F172A
Card: #1E293B
Text Primary: #F1F5F9
Text Secondary: #94A3B8
Border: #334155
Shadows: Stronger (more visible on dark)
```

---

## 8. Loading & Performance

### Loading States

```
Skeleton Screen: Pulsing gray placeholder
Spinner: Animated rotation + "Connecting to PLC..."
Progress Bar: For long operations (show estimated time)
```

### Performance Targets

```
Page Load: <2s (cold start)
Navigation: <100ms (tab switching)
Chart Render: <200ms (50+ data points)
Export: <3s (1000 cycles)
Query Response: <500ms (SQLite)
```

---

## 9. First-Run Wizard

```
Step 1: Welcome
  "Set up your first machine"
  [Next >]

Step 2: Machine Info
  Machine ID: ________________
  Machine Name: ________________
  [< Back] [Next >]

Step 3: Protocol
  Protocol: [OPC-UA ▼]
  [Test Connection] ✓
  [< Back] [Next >]

Step 4: Steps
  Step 1: Loading
  Step 2: Setup
  Step 3: Execute
  ...
  [< Back] [Finish]

Step 5: Success!
  "Machine ready to collect data"
  [Go to Dashboard] [Add Another]
```

---

## 10. Component Checklist

### Must-Have (Phase 3)

- [x] Header (logo, search, profile)
- [x] Sidebar navigation
- [x] Buttons (primary, secondary, danger)
- [x] Input fields (text, dropdown, number)
- [x] Cards & sections
- [x] Data tables (sortable, paginated)
- [x] Modals & dialogs
- [x] Toast notifications
- [x] Status indicators
- [x] Progress bar & spinner
- [x] Tabs
- [x] Charts (line, bar, pie)
- [x] Gantt timeline widget
- [x] Step progress indicator

### Nice-to-Have (Phase 4+)

- [ ] Drag & drop
- [ ] Date picker
- [ ] Toggle switch
- [ ] Range slider
- [ ] Context menu
- [ ] Breadcrumbs
- [ ] Code editor

---

## 11. Error Handling

### User-Friendly Error Messages

```
❌ "Connection failed"
   What went wrong: "PLC at 192.168.1.10:4840 did not respond"
   What to do: "Check network cable and restart PLC"
   [Retry] [Details]

❌ "Cycle data corrupted"
   What went wrong: "Step 3 timestamp is invalid"
   What to do: "Check PLC system clock"
   [Reload] [Details]
```

### Empty States

```
No Cycles Yet:
  "Start your machine"
  [Connect Machine]
```

---

## 12. PyQt6 Implementation Example

```python
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt

class DesignTokens:
    COLOR_PRIMARY = "#2563EB"
    COLOR_SUCCESS = "#059669"
    COLOR_ERROR = "#DC2626"
    SPACING_MD = 12
    FONT_SIZE_BODY = 14

button = QPushButton("Export")
button.setStyleSheet(f"""
    QPushButton {{
        background-color: {DesignTokens.COLOR_PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: {DesignTokens.FONT_SIZE_BODY}px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #1D4ED8;
    }}
""")
```

---

**Document Owner:** UX/Design Lead  
**Last Updated:** 2026-05-02  
**Design System Version:** 1.0-Beta
