# resources/ — Static assets

Non-code assets bundled with the platform. Loaded at runtime via
`importlib.resources` (preferred) or `Path` lookup from project root.

## Structure

```
resources/
├── icons/         # SVG/PNG for PyQt6 desktop + PWA web HMI
├── fonts/         # Custom fonts for HMI display (license-clean only)
└── translations/  # i18n .ts/.qm files (English + Vietnamese day-1)
```

## Conventions

- **Never commit copyrighted vendor assets** (Siemens / Rockwell logos, PLC manuals)
- All icons must be SVG-first; PNG only as fallback for legacy widgets
- Translations follow Qt Linguist `.ts` format (compiled to `.qm` at build time)
- Same icon set used by both PyQt6 desktop and PWA web frontend (single source of truth)

## i18n languages

| Language | Code | Status |
|---|---|---|
| English | en | Default |
| Vietnamese | vi | Day-1 (Ha is Vietnamese; engineers + operators native) |
| Thai | th | Phase 4 (regional expansion) |
