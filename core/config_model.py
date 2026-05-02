"""Pydantic schema for machine YAML configuration.

Validates the YAML file and converts it into the core MachineConfig
dataclass. Adding a new section here is the only place a YAML field
needs to be declared.

Architecture layer: CORE
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .data_model import MachineConfig, ProtocolConfig, ReplayTagDef


class StepConfig(BaseModel):
    index: int = Field(..., ge=1)
    name: str


class MachineSection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True


class ProtocolSection(BaseModel):
    type: str
    url: str
    namespace: Optional[int] = None
    cycle_ready_tag: str = Field("CycleReady")
    cycle_reset_tag: str = Field("CycleReset")
    cycle_log_tag: str = Field("DB_CycleLog")

    # Simulator mode for hardware-free dev/test (Phase 1 scaffold)
    simulator: bool = False
    simulator_cycle_ms: int = Field(5000, ge=100)
    simulator_jitter_ms: int = Field(200, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value.strip().lower()


class CycleAnalyzerSection(BaseModel):
    enabled: bool = True
    total_steps: int = Field(..., ge=1)
    steps: List[StepConfig] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_step_count(self):
        if len(self.steps) != self.total_steps:
            raise ValueError(
                "cycle_analyzer.total_steps must equal the number of step entries"
            )
        return self


class OEEAnalyzerSection(BaseModel):
    enabled: bool = False
    window_minutes: int = Field(60, ge=1)
    # 0 = use rolling minimum cycle as the ideal (conservative).
    ideal_cycle_ms: float = Field(0.0, ge=0.0)

    model_config = ConfigDict(extra="forbid")


class EventLogSection(BaseModel):
    enabled: bool = False

    model_config = ConfigDict(extra="forbid")


class StorageSection(BaseModel):
    mode: str = Field("sqlite")
    sqlite_path: Optional[str] = None
    postgres_dsn: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"sqlite", "postgres"}:
            raise ValueError("storage.mode must be 'sqlite' or 'postgres'")
        return value


class ReplayTagSchema(BaseModel):
    """One tag captured at every step boundary for Replay Mode (F-005)."""

    name: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    kind: str = "number"
    unit: str = ""

    model_config = ConfigDict(extra="forbid")

    @field_validator("kind")
    @classmethod
    def _normalize_kind(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"number", "bool", "string"}:
            raise ValueError("replay tag kind must be number | bool | string")
        return v


class ReplaySection(BaseModel):
    enabled: bool = False
    tags: List[ReplayTagSchema] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LicensingSection(BaseModel):
    """Tier-gating declaration on the machine config."""

    tier_required: str = "tier_1"

    model_config = ConfigDict(extra="forbid")

    @field_validator("tier_required")
    @classmethod
    def _normalize_tier(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("tier_required must not be empty")
        return v


class MachineConfigSchema(BaseModel):
    machine: MachineSection

    # F-004: accept either singular `protocol:` (backward compat) or
    # `protocols:` list.  The validator normalises to `protocols`.
    protocol: Optional[ProtocolSection] = None
    protocols: List[ProtocolSection] = Field(default_factory=list)

    cycle_analyzer: CycleAnalyzerSection
    oee_analyzer: OEEAnalyzerSection = Field(default_factory=OEEAnalyzerSection)
    event_log: EventLogSection = Field(default_factory=EventLogSection)
    storage: StorageSection = Field(default_factory=StorageSection)
    replay: ReplaySection = Field(default_factory=ReplaySection)
    licensing: LicensingSection = Field(default_factory=LicensingSection)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_protocols(self):
        """Merge singular `protocol` into `protocols` list."""
        if self.protocol is not None:
            if self.protocols:
                raise ValueError(
                    "Provide either 'protocol' or 'protocols', not both"
                )
            self.protocols = [self.protocol]
            self.protocol = None
        if not self.protocols:
            raise ValueError("At least one protocol must be configured")
        # Phase 1: enforce N=1 — remove this guard in Phase 4.
        if len(self.protocols) > 1:
            raise ValueError(
                f"Phase 1 supports max 1 protocol per machine, got {len(self.protocols)}"
            )
        return self

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "MachineConfigSchema":
        with yaml_path.open("r", encoding="utf-8") as stream:
            raw_data = yaml.safe_load(stream)

        if raw_data is None:
            raise ValueError(f"Machine config file is empty: {yaml_path}")

        return cls.model_validate(raw_data)

    def to_machine_config(self) -> MachineConfig:
        return MachineConfig(
            machine_id=self.machine.id,
            machine_name=self.machine.name,
            enabled=self.machine.enabled,
            protocols=[
                ProtocolConfig(
                    type=p.type,
                    url=p.url,
                    namespace=p.namespace,
                    cycle_ready_tag=p.cycle_ready_tag,
                    cycle_reset_tag=p.cycle_reset_tag,
                    cycle_log_tag=p.cycle_log_tag,
                    simulator=p.simulator,
                    simulator_cycle_ms=p.simulator_cycle_ms,
                    simulator_jitter_ms=p.simulator_jitter_ms,
                )
                for p in self.protocols
            ],
            cycle_enabled=self.cycle_analyzer.enabled,
            total_steps=self.cycle_analyzer.total_steps,
            step_names=[step.name for step in self.cycle_analyzer.steps],
            oee_enabled=self.oee_analyzer.enabled,
            oee_window_minutes=self.oee_analyzer.window_minutes,
            oee_ideal_cycle_ms=self.oee_analyzer.ideal_cycle_ms,
            event_log_enabled=self.event_log.enabled,
            storage_mode=self.storage.mode,
            sqlite_path=self.storage.sqlite_path,
            postgres_dsn=self.storage.postgres_dsn,
            replay_enabled=self.replay.enabled,
            replay_tags=[
                ReplayTagDef(
                    name=t.name, address=t.address, kind=t.kind, unit=t.unit
                )
                for t in self.replay.tags
            ],
            tier_required=self.licensing.tier_required,
        )
