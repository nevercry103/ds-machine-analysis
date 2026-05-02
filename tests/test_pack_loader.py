"""Pack Loader tests — discovery, manifest validation, isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pack_loader import PackLoader, PackManifest


def _write_manifest(folder: Path, **overrides) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {
        "pack_id": folder.name,
        "version": "1.0.0",
        "machine_class": "test",
        "description": "test pack",
        "supported_plc_brands": ["siemens_s7"],
        "default_steps": 3,
        "tier_required": "tier_1",
        "author": "tester",
        "license": "Proprietary",
    }
    manifest.update(overrides)
    (folder / "pack_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_discover_returns_packs_in_directory(tmp_path: Path):
    _write_manifest(tmp_path / "alpha")
    _write_manifest(tmp_path / "beta")

    packs = PackLoader([tmp_path]).discover()
    pack_ids = sorted(p.pack_id for p in packs)
    assert pack_ids == ["alpha", "beta"]


def test_discover_skips_template_packs(tmp_path: Path):
    """`is_template: true` packs are skipped (they're starter folders)."""
    _write_manifest(tmp_path / "real_pack")
    _write_manifest(
        tmp_path / "_template", pack_id="_template", is_template=True
    )
    # Folders prefixed with _ are also skipped by HIDDEN_PREFIXES — both
    # signals add up to "this is not a real pack."

    packs = PackLoader([tmp_path]).discover()
    assert [p.pack_id for p in packs] == ["real_pack"]


def test_discover_skips_hidden_folders(tmp_path: Path):
    _write_manifest(tmp_path / "real_pack")
    _write_manifest(tmp_path / ".hidden", pack_id="hidden")

    packs = PackLoader([tmp_path]).discover()
    assert [p.pack_id for p in packs] == ["real_pack"]


def test_discover_skips_invalid_manifest(tmp_path: Path):
    _write_manifest(tmp_path / "good")
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "pack_manifest.json").write_text("{not json", encoding="utf-8")

    # Discovery must not raise — bad pack is logged and skipped.
    packs = PackLoader([tmp_path]).discover()
    assert [p.pack_id for p in packs] == ["good"]


def test_duplicate_pack_id_keeps_first(tmp_path: Path):
    other_root = tmp_path / "other_root"
    _write_manifest(tmp_path / "alpha")
    _write_manifest(other_root / "duplicate", pack_id="alpha")

    packs = PackLoader([tmp_path, other_root]).discover()
    assert [p.pack_id for p in packs] == ["alpha"]
    # The first one (in tmp_path/alpha) wins.
    assert packs[0].path == tmp_path / "alpha"


def test_manifest_rejects_unsafe_pack_id():
    with pytest.raises(ValueError):
        PackManifest.model_validate(
            {
                "pack_id": "bad/id",
                "version": "1.0.0",
                "machine_class": "x",
            }
        )


def test_get_returns_pack_by_id(tmp_path: Path):
    _write_manifest(tmp_path / "alpha")
    _write_manifest(tmp_path / "beta")

    loader = PackLoader([tmp_path])
    assert loader.get("alpha").pack_id == "alpha"
    assert loader.get("beta").pack_id == "beta"
    assert loader.get("does_not_exist") is None


def test_shipped_reference_packs_are_valid():
    """The 3 reference packs we ship in repo must load cleanly."""
    loader = PackLoader([Path("packs")])
    pack_ids = sorted(p.pack_id for p in loader.discover())
    for expected in ("cnc_3axis", "bottle_filler", "robot_cell"):
        assert expected in pack_ids, f"missing reference pack: {expected}"


def test_shipped_packs_have_sample_yaml():
    loader = PackLoader([Path("packs")])
    for pack in loader.discover():
        assert pack.has_machine_config_sample, (
            f"pack {pack.pack_id} is missing machine_config.yaml.sample"
        )
