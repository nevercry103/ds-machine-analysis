# README — Siemens S7-1500 Implementation

## Template Installation

1. Open TIA Portal project
2. Import `FB_CycleMaster.scl` → Library folder
3. Copy data structures (UDT_StepLog, UDT_CycleLog) to data types
4. Create instance DB (e.g., DB_CycleLog) with DB_CycleLog type
5. Expose via OPC-UA (ns=3 namespace)

## Configuration

In machine config (config/machines/machine_001.yaml):
```yaml
protocol:
  type: "opcua"
  url: "opc.tcp://192.168.1.10:4840"
  namespace: 3
  cycle_ready_tag: "CycleReady"
  cycle_reset_tag: "CycleReset"
  cycle_log_tag: "DB_CycleLog"
```

## Handshake Protocol

```
PLC                    Python
───                    ──────
[Calculate cycle]
CycleReady = TRUE  ──→  Detect
                       Read CycleLog ──→ Process
                       CycleReset = TRUE
              ←───  Acknowledge
CycleReady = FALSE
CycleReset = FALSE
```

## Testing

1. Create test cycle in TIA Portal debugger
2. Write CycleReady = TRUE
3. Run Python: `asyncua_driver.read_cycle_log()`
4. Verify cycle data matches PLC values ± tolerance

## TODO

- [ ] Implement FB_CycleMaster in TIA Portal
- [ ] Test with real S7-1500 hardware
- [ ] Document cycle data structure offsets
