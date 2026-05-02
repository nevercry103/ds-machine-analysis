# packs/ — Machine Type Packs

A **Machine Pack** is a plug-in bundle that pre-configures DS Machine
Analyzer for a specific machine class (CNC, bottle filler, robot cell,
press, injection molder, etc.). Customer drops a pack into `packs/` and
gets 80% of the configuration done before they touch a YAML file.

## Why packs exist

Every PLC analytics tool starts with a blank slate: the engineer must
define every step, every alarm, every dashboard metric for every machine.
This is repetitive across factories. A pack ships:

- Reference machine YAML config (steps, expected cycle times)
- Reference PLC template (SCL/ST already wired for that machine type)
- Pre-tuned dashboard layouts (which KPIs matter for that machine)
- Common alarm taxonomy + downtime reason codes

## Pack boundary rule (mirrors ds-vision)

**Platform code NEVER imports from `packs/`.** Packs extend the platform;
the platform must remain customer-agnostic.

- Platform modules (`core/`, `plc/`, `storage/`, `api/`, `ui/`, `utils/`) are machine-class-agnostic
- Packs CAN import from platform — pack extends platform, this is correct
- Platform CANNOT import from packs — prevents customer/vendor lock-in

If platform code references a specific pack, rebuilding for a new customer
means modifying the platform = product rot. Strict boundary keeps the
platform shippable as a single binary.

## Pack structure

```
packs/
├── _template/                     ← copy this folder, rename, customize
│   ├── pack_manifest.json
│   ├── README.md
│   ├── machine_config.yaml.sample
│   ├── plc_templates/
│   │   ├── siemens_s7/FB_CycleMaster.scl
│   │   └── codesys/FB_CycleMaster.st
│   └── dashboards/
│       └── default_layout.json
│
├── cnc_3axis/                     ← shipped pack, in repo
├── bottle_filler/                 ← shipped pack
├── robot_cell/                    ← shipped pack
└── customer_<acme>/               ← gitignored — customer-specific deployment
```

## Pack manifest

Every pack must have a valid `pack_manifest.json`:

```json
{
  "pack_id": "cnc_3axis",
  "version": "1.0.0",
  "machine_class": "cnc",
  "description": "3-axis CNC milling — typical 5-step cycle",
  "supported_plc_brands": ["siemens_s7", "fanuc"],
  "default_steps": 5,
  "tier_required": "tier_1",
  "author": "DS Automation",
  "license": "Proprietary"
}
```

## Pack loading

Platform discovers packs at startup via `core/pack_loader.py` (planned —
see `_template/` for shape).

- Scans `packs/` for folders with valid `pack_manifest.json`
- Folders starting with `_` or `.` skipped (templates, hidden)
- Invalid manifest: log warning, skip, platform continues (fail-safe)

## Decision guide: platform feature vs. pack

| Question | Platform | Pack |
|---|---|---|
| "Every machine needs this" | ✅ | ❌ |
| "Specific to one machine type" | ❌ | ✅ |
| "Customer-specific data" | ❌ | ✅ (under `customer_*/`) |
| "Shared across products (Vision + Machine)" | ❌ — DS shared lib | ❌ |
| "Enables a sales conversation" | maybe | ✅ — packs are the App Store moat |

## Future: Pack marketplace

Long-term play (Phase 5+): community / partner-contributed packs published
under DS verification, similar to PLC vendor function-block libraries.
This is the network-effect moat.
