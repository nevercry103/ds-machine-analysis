# Tier Profiles — License Feature Gating

A **tier** declares (a) capacity limits and (b) feature flags. The
platform loads exactly one tier at startup and refuses to register a
machine whose `tier_required` exceeds the loaded tier.

## Shipped tiers

| Tier            | Machines | Replay (h) | OEE | Event Log | Multi-PLC |
|-----------------|---------:|-----------:|:---:|:---------:|:---------:|
| `tier_1`        |        1 |          0 |  ❌ |     ❌    |     ❌    |
| `tier_5`        |        5 |         24 |  ✅ |     ✅    |     ❌    |
| `tier_unlimited`|       10 |        720 |  ✅ |     ✅    |     ✅    |

## Tier ordering

Higher tiers are *strict supersets* of lower tiers. Mathematically:
``tier_1 ⊂ tier_5 ⊂ tier_unlimited`` for both feature flags and
capacity. A machine declared `tier_required: tier_5` runs on tier_5 or
tier_unlimited; never on tier_1.

## How the platform picks a tier at startup

```
1. If env var DS_MA_TIER is set, use that.
2. Else if config/license.key exists, parse it (Phase 4 — not yet).
3. Else default to `tier_unlimited` (development mode, all features on).
```

## How a machine declares its requirement

```yaml
# config/machines/your_machine.yaml
licensing:
  tier_required: tier_5    # platform refuses if loaded tier < tier_5
```

If `licensing` is omitted, the machine implicitly requires `tier_1`.

## Why we ship every tier as a separate YAML, not one constants file

- Customers can deploy a single tier file and audit the feature flags.
- Future per-customer custom tiers (`tier_pharma_compliance`) drop in as
  a new YAML — zero Python changes.
- Same shape as ds-vision's `config/tier_profiles/`.
