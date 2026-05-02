"""Pydantic wire-format schemas for the API.

These are the public contract — they are versioned and may differ from
internal `core.data_model` dataclasses. Never serialize core dataclasses
directly; always pass through a schema in this package.
"""
