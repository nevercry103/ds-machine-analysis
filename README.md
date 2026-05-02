# DS Machine Analyzer — Project Structure

```
ds_machine_analyzer/
├── core/                      ← Core engine (pure Python, no Qt)
│   ├── __init__.py
│   ├── data_model.py         ← Single source of truth (dataclasses)
│   ├── machine_registry.py   ← Manages up to 10 machines
│   ├── data_bus.py           ← Event stream (PLC → pillars)
│   ├── cycle_processor.py    ← Pillar 1 (cycle analytics)
│   ├── oee_processor.py      ← Pillar 2 (OEE) — STUB
│   └── event_logger.py       ← Pillar 3 (event log) — STUB
│
├── protocols/                 ← Protocol adapters
│   ├── __init__.py
│   ├── base_adapter.py       ← Abstract base class
│   ├── opcua_adapter.py      ← OPC-UA (pilot)
│   ├── modbus_adapter.py     ← Modbus — stub
│   ├── ethernet_ip_adapter.py ← EtherNet/IP — stub
│   ├── mc_protocol_adapter.py ← Mitsubishi — stub
│   └── ads_adapter.py        ← Beckhoff — stub
│
├── storage/                   ← Storage backends
│   ├── __init__.py
│   ├── base_storage.py       ← Abstract base class
│   ├── sqlite_storage.py     ← Mode 3 (laptop)
│   └── postgres_storage.py   ← Mode 1 & 2 (server)
│
├── ui/                        ← PyQt6 GUI layer
│   ├── __init__.py
│   ├── main_window.py        ← Main application window
│   └── widgets/
│       ├── __init__.py
│       ├── machine_manager.py ← Add/config/monitor machines
│       ├── cycle_gantt.py     ← Gantt chart visualization
│       ├── oee_dashboard.py   ← OEE metrics — stub
│       └── event_log_view.py  ← Event log view — stub
│
├── plc_templates/            ← OT templates (import to PLC)
│   ├── TEMPLATE_STANDARD.md  ← Chuẩn chung
│   ├── siemens_s7/
│   │   ├── FB_CycleMaster.scl
│   │   └── README_TIAPortal.md
│   ├── codesys/
│   │   ├── FB_CycleMaster.st
│   │   └── README_Codesys.md
│   ├── beckhoff/             ← Planned
│   ├── mitsubishi/           ← Planned
│   └── ...
│
├── config/                    ← Machine configurations
│   ├── machines/
│   │   └── machine_001.yaml.sample
│   └── ...
│
├── data/                      ← Runtime data
│   ├── *.db                  ← SQLite files
│   └── exports/
│
├── logs/                      ← Application logs
│   └── ds_machine_analyzer.log
│
├── tests/                     ← Unit & integration tests
│   └── ...
│
├── main.py                    ← Entry point
├── __init__.py
├── requirements.txt           ← Dependencies
├── CLAUDE.md                  ← This file — project context
└── README.md                  ← User documentation
```

## Key Design Principles

### 1. Core Independence
- Core layer has **zero Qt dependencies** — headless testable
- All I/O is async (asyncio)
- dataclass-based models (Pydantic for validation possible in future)

### 2. Protocol Abstraction
- All protocol adapters inherit `BaseProtocolAdapter`
- Adapter is **stateless** — receives handshake from PLC, reads cycle data, publishes to bus
- Business logic stays in `cycle_processor` — not in adapter

### 3. Storage Abstraction
- SQLite for development/commissioning
- PostgreSQL for production (Mode 1 & 2)
- Same async interface — implementation swaps in config

### 4. Configuration Over Code
- Machine configuration in YAML (1 file per machine)
- Step configs loaded from YAML
- No hardcoded IP, tag names, step counts
- **Add new step**: edit YAML, no Python changes

### 5. Pillars Architecture
- Pillar 1 (Cycle Analyzer) — **pilot**, fully implemented
- Pillar 2 (OEE) — stub, planned
- Pillar 3 (Event Log) — stub, planned
- All pillars consume from same data bus

### 6. Timestamp at PLC
- Timestamp calculated at PLC (≤10ms accuracy)
- Python reads timestamp value from PLC, doesn't recalculate
- Network latency doesn't affect cycle time accuracy

## Deployment Modes (Same Code, Different Config)

| Mode | Deployment | Database | Use Case |
|------|-----------|----------|----------|
| 1 | DS Cloud (multi-tenant) | PostgreSQL | SaaS service |
| 2 | On-Premise (customer site) | PostgreSQL | Dedicated server |
| 3 | Local Laptop | SQLite | Commissioning / engineering |

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run with GUI (PyQt6)
python main.py

# Run headless (stub — not yet implemented)
# python main.py --headless --config config/machines/machine_001.yaml
```

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=core tests/
```

## Contributing

See `CLAUDE.md` for architecture decisions and coding rules.
