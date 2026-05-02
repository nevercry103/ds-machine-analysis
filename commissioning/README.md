# commissioning/ — On-site PLC bench scripts

Numbered helper scripts the DS engineer runs **at the customer factory**
during initial setup, before the full platform is configured. Each script
is standalone — runs with just `python commissioning/<NN>_<name>.py` and
reads no platform config.

## Convention (mirrors ds-vision/camera/0X_*.py)

| # | Script | Purpose |
|---|---|---|
| 00 | `00_network_check.py` | Ping PLC, verify subnet, packet size |
| 01 | `01_opcua_connect_test.py` | OPC-UA: connect, browse namespace |
| 02 | `02_opcua_handshake_test.py` | Drive `CycleReady` flag, read CycleLog DB |
| 03 | `03_modbus_connect_test.py` | Modbus TCP: read holding registers |
| 04 | `04_ads_connect_test.py` | Beckhoff ADS connect |
| 05 | `05_mc_protocol_test.py` | Mitsubishi MC connect |
| 06 | `06_cycle_capture_smoke.py` | Bench end-to-end: PLC → adapter → SQLite — 10 cycles |

## Why separate from `scripts/`

- `scripts/` = developer tools (build, audit, generate)
- `commissioning/` = field engineer tools (run on customer's laptop on customer's network)
- Different audience, different stability bar (commissioning scripts must work on locked-down factory PCs with no internet)

## Rules

- No external dependencies beyond what's in `requirements.txt`
- Print output is operator-readable (status icons OK / FAIL, plain English)
- Exit codes: `0` = pass, `1` = config issue, `2` = network issue, `3` = PLC unreachable
- Never modify customer PLC values without confirmation prompt
