"""Tier profile + gating tests."""

from __future__ import annotations

import pytest

from core.tier_profile import (
    TierError,
    list_available_tiers,
    load_tier,
    validate_machine_requirements,
)


def test_shipped_tiers_load():
    tiers = list_available_tiers()
    assert sorted(tiers) == ["tier_1", "tier_5", "tier_unlimited"]


def test_tier_1_caps_features():
    tier = load_tier("tier_1")
    assert tier.max_machines == 1
    assert tier.has_feature("cycle_variance")
    assert not tier.has_feature("replay_mode")
    assert not tier.has_feature("oee_analytics")
    assert tier.replay_retention_hours == 0


def test_tier_5_unlocks_replay_and_oee():
    tier = load_tier("tier_5")
    assert tier.max_machines == 5
    assert tier.has_feature("replay_mode")
    assert tier.has_feature("oee_analytics")
    assert tier.replay_retention_hours == 24
    assert not tier.has_feature("multi_plc_per_machine")  # tier_unlimited


def test_tier_unlimited_has_everything():
    tier = load_tier("tier_unlimited")
    assert tier.max_machines == 10
    assert tier.has_feature("multi_plc_per_machine")
    assert tier.replay_retention_hours == 720


def test_tier_ordering():
    t1 = load_tier("tier_1")
    t5 = load_tier("tier_5")
    tu = load_tier("tier_unlimited")

    assert tu.allows("tier_1") and tu.allows("tier_5") and tu.allows("tier_unlimited")
    assert t5.allows("tier_1") and t5.allows("tier_5") and not t5.allows("tier_unlimited")
    assert t1.allows("tier_1") and not t1.allows("tier_5") and not t1.allows("tier_unlimited")


def test_validate_refuses_higher_tier_machine():
    """A machine declaring tier_required: tier_5 must NOT load on tier_1."""
    tier = load_tier("tier_1")
    with pytest.raises(TierError, match="tier_5"):
        validate_machine_requirements(
            tier,
            machine_id="m_high",
            tier_required="tier_5",
            total_steps=3,
            replay_enabled=False,
            current_machine_count=0,
        )


def test_validate_refuses_capacity_overflow():
    tier = load_tier("tier_1")  # max_machines=1
    with pytest.raises(TierError, match="max 1 machines"):
        validate_machine_requirements(
            tier,
            machine_id="m_extra",
            tier_required="tier_1",
            total_steps=3,
            replay_enabled=False,
            current_machine_count=1,
        )


def test_validate_refuses_replay_on_tier_1():
    tier = load_tier("tier_1")
    with pytest.raises(TierError, match="Replay Mode"):
        validate_machine_requirements(
            tier,
            machine_id="m_replay",
            tier_required="tier_1",
            total_steps=3,
            replay_enabled=True,
            current_machine_count=0,
        )


def test_validate_refuses_too_many_steps():
    tier = load_tier("tier_1")  # max_steps_per_machine=10
    with pytest.raises(TierError, match="caps at"):
        validate_machine_requirements(
            tier,
            machine_id="m_big",
            tier_required="tier_1",
            total_steps=999,
            replay_enabled=False,
            current_machine_count=0,
        )


def test_validate_passes_when_within_limits():
    tier = load_tier("tier_5")
    validate_machine_requirements(
        tier,
        machine_id="m_ok",
        tier_required="tier_1",  # lower than loaded
        total_steps=10,
        replay_enabled=True,  # tier_5 has replay_mode
        current_machine_count=0,
    )  # no exception = pass


def test_unknown_tier_raises():
    with pytest.raises(TierError):
        load_tier("tier_does_not_exist")
