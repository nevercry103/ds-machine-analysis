# PLC Templates — OT Standard

This folder contains hardware-agnostic PLC templates for different vendors.

## Principle

All templates share the same **logic** (FB_CycleMaster, cycle calculation).
Only the **system time function** changes per vendor.

```
Template Structure (same for all vendors)
├── UDT_StepLog        ← step data structure (identical)
├── UDT_CycleLog       ← cycle container (identical)
├── FB_CycleMaster     ← logic block (identical except 1 line for system time)
└── DB_CycleLog        ← instance data (expose via protocol)
```

## Vendor-Specific — System Time Functions

| Vendor | Platform | Language | Time Function |
|--------|----------|----------|---------------|
| Siemens | S7-1500 / S7-1200 | SCL | `RD_SYS_T()` |
| Codesys | universal | ST | `GET_DATE_AND_TIME()` |
| Beckhoff | TwinCAT | ST | `F_GetSystemTime()` |
| Mitsubishi | iQ-R / iQ-F | ST | SD210-SD213 registers |
| Allen-Bradley | CompactLogix / ControlLogix | ST | `GSV` instruction |
| OMRON | CJ / NX | ST | `GetSysInfo()` |

## Templates by Status

- `siemens_s7/` — **PILOT** (Siemens S7-1500)
- `codesys/` — PLANNED
- `beckhoff/` — PLANNED (Beckhoff TwinCAT)
- `mitsubishi/` — PLANNED (Mitsubishi iQ series)
- `allen_bradley/` — PLANNED (Compact Logix)
- `omron/` — PLANNED

## Implementation Steps

When adding a new template:

1. Copy `FB_CycleMaster.st` from reference (e.g., Codesys)
2. Replace system time function with vendor-specific call
3. Export to `.scl`, `.st`, or vendor format
4. Add README_[Vendor].md with import instructions
5. Test with real hardware (no simulator) if possible

## Key Rules

✓ **DO** maintain identical logic across all templates
✓ **DO** timestamp at PLC (≤10ms accuracy)
✓ **DO** implement same handshake protocol

✗ **DON'T** add vendor-specific shortcuts that break portability
✗ **DON'T** calculate timestamp in Python
✗ **DON'T** hardcode IP addresses or tag names in PLC code
