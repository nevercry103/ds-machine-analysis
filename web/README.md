# web/ — Progressive Web App (PWA) HMI

Responsive web frontend — runs on **operator tablet, engineer phone,
manager phone, executive phone**. Same backend (`api/`) as the PyQt6
desktop, different presentation.

## Why PWA, not native iOS/Android

| Capability | PWA | Native (iOS+Android) |
|---|---|---|
| Install to home screen | ✅ | ✅ |
| Push notifications | ✅ Web Push API | ✅ |
| Offline cache | ✅ Service worker | ✅ |
| Camera / scanner access | ✅ | ✅ |
| Codebase count | 1 | 2 |
| App Store gate | ❌ Not needed | ✅ 1-2 weeks per release |
| Update deployment | ✅ Instant | ❌ Users must update |
| Behind factory firewall | ✅ Just a URL | ⚠️ App Store dependency |

PWA wins on every axis except 5% of native polish. Not worth 2x maintenance for SME factory tool.

## Stack

- **Templates:** HTMX + Jinja2 (server-rendered HTML, hypermedia-driven)
- **Styling:** Tailwind CSS (utility-first, small footprint)
- **PWA layer:** Web App Manifest + Service Worker + Web Push
- **Real-time:** WebSocket to `/ws/machines/{id}/events`

> HTMX over SvelteKit: simpler, less JS, fewer build steps. SME
> factories patch their own deployments — keep the stack low-friction.

## Structure

```
web/
├── README.md
├── static/
│   ├── manifest.json        ← PWA install metadata
│   ├── service-worker.js    ← offline cache + push handler
│   ├── icons/               ← 192/512 PWA icons
│   ├── css/
│   │   └── style.css        ← Tailwind compiled output
│   └── js/
│       ├── app.js           ← bootstrap, WS client
│       └── htmx.min.js      ← htmx runtime (vendored)
└── templates/
    ├── base.html            ← layout, navbar, role-aware nav
    ├── index.html           ← machine grid (10 cards)
    ├── machine.html         ← single machine drill-down (Gantt + history)
    └── partials/            ← htmx fragments (server pushes these)
        ├── machine_card.html
        └── cycle_row.html
```

## User flows

### Engineer on phone (walking factory)
1. Open `https://factory-pc:8000/web/` from phone
2. PWA prompts "Install" → adds to home screen
3. See 10 machines as cards, color-coded (green/yellow/red)
4. Tap a card → drill into Gantt, recent cycles, alarms
5. Push notification when machine faults — tap to deep-link

### Operator on tablet (mounted at machine)
1. Tablet opens `https://factory-pc:8000/web/?machine=001` on boot
2. Single-machine kiosk view: current cycle, big OK/NG verdict
3. Stoppage tap UI: one button per downtime reason → tagged in DB
4. JWT scope = `operator` — can ack alarm, tag downtime, no config

### Manager on phone (anywhere on factory wifi)
1. Bookmark `/web/manager` → role-filtered dashboard
2. OEE summary, downtime ranking, daily/shift reports
3. Push notification when OEE drops below threshold

## Rules

- ❌ Never call core/storage/plc directly — always go through `/api/*`
- ✅ Same `resources/icons/` source as PyQt6 desktop (single asset library)
- ✅ All strings i18n via `resources/translations/` (en + vi day-1)
- ✅ Mobile-first CSS — desktop is the secondary target
