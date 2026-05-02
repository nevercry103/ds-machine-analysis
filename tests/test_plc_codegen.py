"""PLC codegen tests — render Siemens SCL and Codesys ST from a config."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config_model import MachineConfigSchema
from core.data_model import MachineConfig
from core.plc_codegen import (
    PlcCodegenError,
    render,
    render_to_file,
    supported_brands,
)


def _sample_config() -> MachineConfig:
    return MachineConfigSchema.from_yaml(
        Path("config/machines/machine_001.yaml.sample")
    ).to_machine_config()


def test_supported_brands_includes_siemens_and_codesys():
    brands = supported_brands()
    # The two we shipped Jinja2 templates for must be discoverable.
    assert "siemens_s7" in brands
    assert "codesys" in brands


def test_render_siemens_contains_step_names():
    config = _sample_config()
    rendered = render(config, "siemens_s7", source_yaml="machine_001.yaml")

    # Every step name from the YAML must appear verbatim in the SCL.
    for step_name in config.step_names:
        assert step_name in rendered, f"missing step name: {step_name}"

    # Handshake tags from config must be present.
    assert config.protocol.cycle_ready_tag in rendered
    assert config.protocol.cycle_reset_tag in rendered
    assert config.protocol.cycle_log_tag in rendered

    # SCL frame markers — confidence that we rendered SCL, not garbage.
    assert "FUNCTION_BLOCK" in rendered
    assert "END_FUNCTION_BLOCK" in rendered
    assert "RD_SYS_T" in rendered

    # Header carries provenance.
    assert "machine_001.yaml" in rendered
    assert config.machine_id in rendered


def test_render_codesys_contains_step_names():
    config = _sample_config()
    rendered = render(config, "codesys")

    for step_name in config.step_names:
        assert step_name in rendered

    assert "FUNCTION_BLOCK FB_CycleMaster" in rendered
    assert "GET_DATE_AND_TIME" in rendered
    assert "DUT_CycleLog" in rendered


def test_render_unknown_brand_raises():
    config = _sample_config()
    with pytest.raises(PlcCodegenError):
        render(config, "no_such_brand")


def test_render_to_file_writes_extension(tmp_path: Path):
    config = _sample_config()
    out = render_to_file(config, "siemens_s7", tmp_path)
    assert out.exists()
    assert out.suffix == ".scl"
    assert out.read_text(encoding="utf-8").startswith("//")


def test_step_count_mismatch_is_caught():
    """If the dataclass total_steps != len(step_names), refuse to render."""
    config = _sample_config()
    bad = MachineConfig(
        machine_id=config.machine_id,
        machine_name=config.machine_name,
        protocols=config.protocols,
        total_steps=99,  # mismatch
        step_names=config.step_names,
    )
    with pytest.raises(PlcCodegenError):
        render(bad, "siemens_s7")
