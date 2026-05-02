# Pack: `bottle_filler`

Reference pack for an **inline bottle-filling** line. 6-step cycle
typical of beverage / pharma SME factories.

## Typical machine

| Step | Name       | Description                               | Expected (ms) |
|-----:|------------|-------------------------------------------|--------------:|
| 1    | Infeed     | Empty bottle arrives on conveyor          | 200-400       |
| 2    | Position   | Bottle indexes under fill nozzle          | 300-500       |
| 3    | Fill       | Liquid dispense (volumetric or weight)    | 800-1500      |
| 4    | Cap        | Cap pickup + torque tightening            | 400-700       |
| 5    | Label      | Pressure-sensitive label applied          | 300-500       |
| 6    | Discharge  | Filled bottle ejected to downstream conv. | 150-300       |

## Why this pack matters

Bottle fillers are the **highest-volume use case** for SME OEE platforms:
30-150 ppm, 24/7 operation, where Cycle Variance directly predicts
fill-quality drift. The default tier_1 license is sufficient.

## Quick start

```bash
cp packs/bottle_filler/machine_config.yaml.sample \
   config/machines/filler_001.yaml

python scripts/generate_plc_template.py \
    --config config/machines/filler_001.yaml \
    --brand siemens_s7
```
