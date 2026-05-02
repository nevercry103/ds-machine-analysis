"""YAML machine configuration loader.

Single source of truth for loading machine YAML files into validated
Pydantic models defined in `core.config_model`. Use this instead of
`yaml.safe_load()` directly so validation is consistent.
"""

from __future__ import annotations

from pathlib import Path

from core.config_model import MachineConfigSchema
from core.data_model import MachineConfig
from utils.logger import log


def load_machine_config(path: str | Path) -> MachineConfig:
    """Load and validate a single machine YAML config.

    Raises:
        FileNotFoundError: path does not exist.
        pydantic.ValidationError: YAML structure violates MachineConfig schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Machine config not found: {path}")

    schema = MachineConfigSchema.from_yaml(path)
    config = schema.to_machine_config()
    log.info(
        "Loaded machine config",
        machine_id=config.machine_id,
        protocol=config.protocol.type,
        path=str(path),
    )
    return config


def load_all_machine_configs(machines_dir: str | Path) -> list[MachineConfig]:
    """Load every YAML file in `config/machines/` (excluding `.sample`)."""
    machines_dir = Path(machines_dir)
    configs: list[MachineConfig] = []
    for yml in sorted(machines_dir.glob("*.yaml")):
        if yml.name.endswith(".sample"):
            continue
        configs.append(load_machine_config(yml))
    log.info(f"Loaded {len(configs)} machine config(s) from {machines_dir}")
    return configs
