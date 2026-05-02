"""Pack discovery and manifest loading.

A **Machine Pack** is a plug-in bundle that pre-configures DS Machine
Analyzer for a specific machine class (CNC, bottle filler, robot cell).
At startup the platform scans ``packs/`` for folders containing a valid
``pack_manifest.json``.

Strict boundary rule (mirrors ds-vision):
    Platform code never imports from ``packs/``. Packs CAN import from
    platform; the platform CANNOT import from any specific pack. This
    keeps the platform shippable as a single binary.

This module *reads* pack manifests and lists available pack metadata.
It does NOT execute pack code. Pack-specific tools/dashboards are
loaded lazily by their own systems when (and only when) a recipe asks
for them.

Architecture layer: CORE
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils.logger import log


class PackManifest(BaseModel):
    """Validated `pack_manifest.json` contents.

    `extra="ignore"` so packs can carry forward-compatible custom fields
    without breaking older platform versions.
    """

    pack_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    machine_class: str = Field(..., min_length=1)
    description: str = ""
    supported_plc_brands: list[str] = Field(default_factory=list)
    default_steps: int = Field(0, ge=0)
    tier_required: str = "tier_1"
    author: str = ""
    license: str = ""
    is_template: bool = False

    model_config = ConfigDict(extra="ignore")

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        # Pack IDs become folder names — keep them filesystem-safe.
        bad = set(value) & set(' /\\:?*"<>|')
        if bad:
            raise ValueError(
                f"pack_id contains illegal character(s): {''.join(bad)!r}"
            )
        return value


class Pack(BaseModel):
    """A discovered pack: manifest + filesystem location."""

    manifest: PackManifest
    path: Path

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def pack_id(self) -> str:
        return self.manifest.pack_id

    @property
    def has_plc_template(self) -> bool:
        return any((self.path / "plc_templates").glob("*/FB_CycleMaster.*"))

    @property
    def has_machine_config_sample(self) -> bool:
        return (self.path / "machine_config.yaml.sample").exists()


class PackLoader:
    """Discovers packs in one or more roots.

    Default root is ``<project>/packs``. Customer-specific packs live in
    folders prefixed ``customer_*`` (gitignored — see ``.gitignore``).
    """

    MANIFEST_FILENAME = "pack_manifest.json"
    HIDDEN_PREFIXES = ("_", ".")

    def __init__(self, roots: list[str | Path]) -> None:
        self.roots = [Path(r) for r in roots]

    def discover(self) -> list[Pack]:
        """Scan every root and return discovered packs.

        Errors in one pack don't prevent discovery of others. Invalid
        manifests are logged at WARNING and skipped.
        """
        found: list[Pack] = []
        seen_ids: set[str] = set()

        for root in self.roots:
            if not root.exists():
                log.debug("Pack root does not exist", path=str(root))
                continue
            for entry in sorted(root.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith(self.HIDDEN_PREFIXES):
                    continue
                manifest_path = entry / self.MANIFEST_FILENAME
                if not manifest_path.exists():
                    continue
                try:
                    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest = PackManifest.model_validate(raw)
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "Invalid pack manifest, skipping",
                        path=str(manifest_path),
                        error=str(exc),
                    )
                    continue

                if manifest.is_template:
                    log.debug(
                        "Skipping template pack (is_template=true)",
                        pack_id=manifest.pack_id,
                    )
                    continue

                if manifest.pack_id in seen_ids:
                    log.warning(
                        "Duplicate pack_id, ignoring later occurrence",
                        pack_id=manifest.pack_id,
                        path=str(entry),
                    )
                    continue

                seen_ids.add(manifest.pack_id)
                found.append(Pack(manifest=manifest, path=entry))

        log.info("Pack discovery complete", count=len(found))
        return found

    def get(self, pack_id: str) -> Pack | None:
        """Locate one pack by id (re-scans every call — packs are small)."""
        for pack in self.discover():
            if pack.pack_id == pack_id:
                return pack
        return None
