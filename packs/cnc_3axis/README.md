# Pack: `cnc_3axis`

Reference pack for **3-axis CNC milling** machines. Ships a typical
5-step cycle, a pre-tuned machine YAML, and brand-agnostic PLC templates
for Siemens / Codesys / Beckhoff.

## Typical machine

| Step | Name        | Description                                | Expected (ms) |
|-----:|-------------|--------------------------------------------|--------------:|
| 1    | Load        | Operator loads workpiece + closes door     | 4000-8000     |
| 2    | Home        | Spindle moves to home position             | 1000-2000     |
| 3    | Rough Cut   | Roughing pass with high feed rate          | 15000-30000   |
| 4    | Finish Cut  | Finishing pass with slow feed rate         | 8000-15000    |
| 5    | Unload      | Door opens, operator removes workpiece     | 3000-6000     |

## Quick start

1. Copy this pack's YAML into your machines folder:

   ```bash
   cp packs/cnc_3axis/machine_config.yaml.sample \
      config/machines/machine_001.yaml
   ```

2. Edit `machine_001.yaml` to set the PLC IP/protocol for your specific machine.

3. Generate the PLC code for your brand:

   ```bash
   python scripts/generate_plc_template.py \
       --config config/machines/machine_001.yaml \
       --brand siemens_s7 \
       --output-dir build/plc
   ```

4. Import the generated `.scl` file into TIA Portal as a Function Block.
5. Wire your existing program logic to call `FB_CycleMaster` once per scan, with one `StepStart_<n>` / `StepEnd_<n>` BOOL pulse per cycle phase.

## What this pack provides

| File | Role |
|---|---|
| `pack_manifest.json` | Discovery metadata (loaded by `core/pack_loader.py`) |
| `README.md` | This file |
| `machine_config.yaml.sample` | Drop-in starting point for the machine YAML |
| `dashboards/default_layout.json` | Suggested PWA dashboard widgets (Phase 3) |
