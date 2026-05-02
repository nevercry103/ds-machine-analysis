"""Cross-cutting utilities for DS Machine Analyzer.

Modules in this package are framework-agnostic helpers used across core/,
plc/, storage/, api/, and ui/ layers. Nothing in `utils/` should import
from `ui/`, `api/`, or `core.cycle_processor` to avoid circular dependencies.
"""
