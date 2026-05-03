"""Tier profile — license feature gating for DS Machine Analyzer.

A tier is a (capacity + feature flags) bundle loaded at startup. The
platform refuses to register a machine whose ``tier_required`` exceeds
the loaded tier. Mirrors ds-vision's tier system (F-006).

Architecture layer: CORE
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field

from utils.logger import log

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TIER_DIR = _PROJECT_ROOT / "config" / "tier_profiles"

# Strict subset ordering — tier_X allows everything in tier_Y when X >= Y.
# Stored as a rank so we can do `loaded.rank >= required.rank`.
_TIER_RANK: dict[str, int] = {
    "tier_free": 0,
    "tier_1": 1,
    "tier_5": 2,
    "tier_unlimited": 3,
}


class TierFeatures(BaseModel):
    cycle_analytics: bool = True
    cycle_variance: bool = True
    bottleneck_detection: bool = True
    oee_analytics: bool = False
    event_log: bool = False
    replay_mode: bool = False
    push_notifications: bool = False
    multi_plc_per_machine: bool = False
    pwa_web_hmi: bool = True
    desktop_ui: bool = True

    model_config = ConfigDict(extra="ignore")


class TierProfile(BaseModel):
    """A loaded tier — what the platform reads from disk."""

    tier_id: str = Field(..., min_length=1)
    display_name: str
    description: str = ""
    max_machines: int = Field(..., ge=1)
    max_steps_per_machine: int = Field(..., ge=1)
    features: TierFeatures = Field(default_factory=TierFeatures)
    replay_retention_hours: int = Field(0, ge=0)
    data_retention_days: int = Field(0, ge=0)  # 0 = unlimited

    model_config = ConfigDict(extra="ignore")

    @property
    def rank(self) -> int:
        """Strict-subset ordering — higher rank means higher tier.

        Unknown tier ids fall back to ``0`` so any explicit tier outranks
        them — caller-defined custom tiers should still register a rank
        in `_TIER_RANK` if they want to be comparable.
        """
        return _TIER_RANK.get(self.tier_id, 0)

    def allows(self, required_tier_id: str) -> bool:
        """True if the loaded tier satisfies the requested requirement."""
        required_rank = _TIER_RANK.get(required_tier_id, 0)
        return self.rank >= required_rank

    def has_feature(self, feature: str) -> bool:
        """Lookup a feature flag by name; unknown features = False."""
        return bool(getattr(self.features, feature, False))


class TierError(Exception):
    """Raised when a tier file is missing or a machine exceeds its limits."""


def load_tier(tier_id: str, tier_dir: Path | str | None = None) -> TierProfile:
    """Load one tier YAML by id (`tier_1` -> `tier_1.yaml`)."""
    base = Path(tier_dir) if tier_dir else _DEFAULT_TIER_DIR
    path = base / f"{tier_id}.yaml"
    if not path.exists():
        raise TierError(
            f"Tier '{tier_id}' not found at {path}. "
            f"Available: {[p.stem for p in base.glob('*.yaml')]}"
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    profile = TierProfile.model_validate(data)
    if profile.tier_id != tier_id:
        log.warning(
            "Tier file id mismatch (filename vs tier_id field)",
            file_id=tier_id,
            yaml_id=profile.tier_id,
        )
    return profile


def list_available_tiers(tier_dir: Path | str | None = None) -> list[str]:
    base = Path(tier_dir) if tier_dir else _DEFAULT_TIER_DIR
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.yaml"))


def resolve_current_tier(tier_dir: Path | str | None = None) -> TierProfile:
    """Decide which tier the platform is running with.

    1. ``DS_MA_TIER`` environment variable wins.
    2. Otherwise default to ``tier_unlimited`` — development mode, all
       features on. (Future: read a license file in Phase 4.)
    """
    chosen = os.getenv("DS_MA_TIER", "tier_unlimited").strip().lower()
    profile = load_tier(chosen, tier_dir=tier_dir)
    log.info(
        "Tier loaded",
        tier_id=profile.tier_id,
        max_machines=profile.max_machines,
        replay_mode=profile.features.replay_mode,
    )
    return profile


def validate_machine_requirements(
    tier: TierProfile,
    *,
    machine_id: str,
    tier_required: str,
    total_steps: int,
    replay_enabled: bool,
    current_machine_count: int,
) -> None:
    """Raise `TierError` if registering this machine would exceed the tier.

    Called by `MachineRegistry.register()`. Failures are loud — the
    platform must never silently downgrade a machine onto an inadequate
    license, or the customer ends up with broken expectations.
    """
    if not tier.allows(tier_required):
        raise TierError(
            f"Machine '{machine_id}' requires '{tier_required}' but the "
            f"platform is running on '{tier.tier_id}'. Upgrade the license "
            f"or change the machine's licensing.tier_required."
        )

    if current_machine_count >= tier.max_machines:
        raise TierError(
            f"Cannot register '{machine_id}': tier '{tier.tier_id}' allows "
            f"max {tier.max_machines} machines. Already registered: "
            f"{current_machine_count}."
        )

    if total_steps > tier.max_steps_per_machine:
        raise TierError(
            f"Machine '{machine_id}' has {total_steps} steps but tier "
            f"'{tier.tier_id}' caps at {tier.max_steps_per_machine}."
        )

    if replay_enabled and not tier.has_feature("replay_mode"):
        raise TierError(
            f"Machine '{machine_id}' has replay.enabled=true but tier "
            f"'{tier.tier_id}' does not include Replay Mode."
        )
