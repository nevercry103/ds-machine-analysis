"""
tests/test_config_loader.py

Unit tests for machine YAML configuration loading.
"""

from pathlib import Path
from core.config_model import MachineConfigSchema


def test_machine_config_schema_loads_sample():
    sample_path = Path("config/machines/machine_001.yaml.sample")
    config = MachineConfigSchema.from_yaml(sample_path)

    assert config.machine.id == "machine_001"
    assert len(config.protocols) == 1
    assert config.protocols[0].type == "opcua"
    assert config.cycle_analyzer.total_steps == 5
    assert len(config.cycle_analyzer.steps) == 5
    assert config.storage.mode == "sqlite"
    assert config.storage.sqlite_path == "data/machine_001.db"


def test_machine_config_to_machine_config():
    sample_path = Path("config/machines/machine_001.yaml.sample")
    config = MachineConfigSchema.from_yaml(sample_path)
    machine_config = config.to_machine_config()

    assert machine_config.machine_id == "machine_001"
    assert machine_config.protocol.type == "opcua"
    assert machine_config.storage_mode == "sqlite"
    assert machine_config.sqlite_path == "data/machine_001.db"
