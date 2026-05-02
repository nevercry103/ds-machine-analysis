# scripts/ — DS Machine Analyzer utility scripts

One-off and recurring developer/operator tools that do **not** belong
inside `core/`, `plc/`, `api/`, or `ui/`. Anything in this folder should
be runnable directly:

```bash
python scripts/<name>.py [args]
```

## Conventions

- Each script has a docstring explaining purpose, usage, and exit codes
- Scripts may import from `core/`, `utils/`, `plc/`, `storage/` — never from `ui/`
- Output goes to `output/` or stdout, never overwrites tracked files
- Log via `utils.logger.log`, not `print()`

## Planned scripts

| Script | Purpose |
|---|---|
| `bench_cycle_accuracy.py` | Hardware-in-loop test: compare PLC timestamp vs. Python receive time across 1000 cycles |
| `generate_test_data.py` | Synthesize sample SQLite database for UI development without PLC |
| `generate_plc_template.py` | YAML config → SCL/ST file generator (the "killer feature" — Phase 2) |
| `build.py` | PyInstaller single-binary build (Phase 5) |
| `stamp_version.py` | Inject version + git SHA into `__version__.py` before build |
| `verify_deployment.py` | Smoke-test a deployed instance: API up, DB reachable, PLC ping |
| `run_sonnet_audit.bat` | Batch wrapper to run an LLM-driven code audit (matches ds-vision pattern) |

Add a new script: write the file, add a row above, document in CLAUDE.md key files table if it becomes essential.
