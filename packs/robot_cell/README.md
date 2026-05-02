# Pack: `robot_cell`

Reference pack for a **single-robot pick-and-place cell** — Fanuc / ABB
/ KUKA / Yaskawa coordinated with a cell PLC over OPC-UA or Modbus.

## Typical cycle

| Step | Name      | Description                            | Expected (ms) |
|-----:|-----------|----------------------------------------|--------------:|
| 1    | Pick      | Robot acquires part at infeed          | 600-1000      |
| 2    | Transfer  | Robot motion to fixture                | 800-1200      |
| 3    | Place     | Part placed + grip released            | 400-700       |
| 4    | Retreat   | Robot returns to home                  | 600-900       |

## Notes

- This pack assumes a **cell PLC** drives the StepStart/StepEnd bits.
  The robot itself is treated as a peripheral; its joint trajectories
  are out of scope for cycle analytics.
- For multi-robot cells (>1 robot in one work envelope), use one
  machine_id per robot and aggregate at the line level — the
  one-machine-many-PLC story (F-004) covers the inverse case.
