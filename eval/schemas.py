"""Eval-specific Pydantic models.

All inter-node data in the eval suite is typed. This module imports
RiskCategory and RiskSeverity from the agent's schemas to maintain a
single source of truth for shared enumerations.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from research_agent.schemas import RiskCategory, RiskSeverity


class Tier(StrEnum):
    """Difficulty tier for planted facts."""

    easy = "easy"
    medium = "medium"
    hard = "hard"


class ResearchDimension(StrEnum):
    """Mirrors planner prompt dimensions."""

    biographical = "biographical"
    professional_history = "professional_history"
    financial_connections = "financial_connections"
    network = "network"
    public_statements = "public_statements"
    risk_surface = "risk_surface"


class FactType(StrEnum):
    """Classification of fact content."""

    biographical = "biographical"
    role = "role"
    financial = "financial"
    network = "network"
    statement = "statement"
    risk = "risk"


class MatchStrategy(StrEnum):
    """How to match agent claims against this fact."""

    exact = "exact"
    fuzzy = "fuzzy"
    semantic = "semantic"


class PersonaType(StrEnum):
    """Whether facts are on the plant site or from public sources."""

    synthetic = "synthetic"
    real_public = "real_public"


class PlantedFact(BaseModel):
    """A single ground-truth fact planted for evaluation."""

    id: str = Field(..., description="Pattern: fact_[a-z]\\d{2}")
    statement: str = Field(..., max_length=500)
    difficulty: Tier
    expected_dimension: ResearchDimension
    expected_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    fact_type: FactType
    match_strategy: MatchStrategy = MatchStrategy.fuzzy
    match_threshold: float = Field(default=80.0)
    notes: str
    source_urls: list[str] = Field(..., min_length=1)

    @field_validator("id")
    @classmethod
    def id_must_match_pattern(cls, v: str) -> str:
        if not re.fullmatch(r"fact_[a-z]\d{2}", v):
            raise ValueError("id must match pattern fact_[a-z]\\d{2}")
        return v

    @field_validator("statement")
    @classmethod
    def statement_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("statement must not be empty")
        return v

    @field_validator("source_urls")
    @classmethod
    def source_urls_must_have_at_least_one(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("source_urls must have at least 1 item")
        return v

    @model_validator(mode="after")
    def match_threshold_in_valid_range(self) -> PlantedFact:
        if self.match_strategy == MatchStrategy.fuzzy:
            if not (0 <= self.match_threshold <= 100):
                raise ValueError("fuzzy match_threshold must be in [0, 100]")
        elif self.match_strategy == MatchStrategy.semantic:
            if not (0.0 <= self.match_threshold <= 1.0):
                raise ValueError("semantic match_threshold must be in [0.0, 1.0]")
        return self


class PlantedRisk(BaseModel):
    """A planted risk flag expected to be surfaced by the agent."""

    id: str = Field(..., description="Pattern: risk_[a-z]\\d{2}")
    risk_category: RiskCategory
    expected_severity: RiskSeverity
    description: str
    evidence_source_urls: list[str] = Field(..., min_length=1)

    @field_validator("id")
    @classmethod
    def id_must_match_pattern(cls, v: str) -> str:
        if not re.fullmatch(r"risk_[a-z]\d{2}", v):
            raise ValueError("id must match pattern risk_[a-z]\\d{2}")
        return v

    @field_validator("description")
    @classmethod
    def description_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description must not be empty")
        return v

    @field_validator("evidence_source_urls")
    @classmethod
    def evidence_source_urls_must_have_at_least_one(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("evidence_source_urls must have at least 1 item")
        return v


class PersonaDefinition(BaseModel):
    """Complete definition of an eval persona."""

    id: str = Field(..., description="Pattern: persona_[a-z_]+")
    target_name: str = Field(..., max_length=200)
    target_context: str
    persona_type: PersonaType
    description: str
    ethical_notes: str
    planted_facts: list[PlantedFact] = Field(..., min_length=1)
    planted_risks: list[PlantedRisk] = Field(default_factory=list)
    plant_site_root: str | None = Field(default=None)
    max_iterations: int = Field(default=3, ge=1, le=10)
    max_dollars: float = Field(default=5.0, ge=0.1, le=50.0)

    @field_validator("id")
    @classmethod
    def id_must_match_pattern(cls, v: str) -> str:
        if not re.fullmatch(r"persona_[a-z_]+", v):
            raise ValueError("id must match pattern persona_[a-z_]+")
        return v

    @field_validator("target_name")
    @classmethod
    def target_name_must_be_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("target_name must not be empty")
        if len(v) > 200:
            raise ValueError("target_name must not exceed 200 characters")
        return v

    @model_validator(mode="after")
    def synthetic_must_have_plant_site_root(self) -> PersonaDefinition:
        if self.persona_type == PersonaType.synthetic and not self.plant_site_root:
            raise ValueError("plant_site_root is required when persona_type is synthetic")
        return self


class FactMatch(BaseModel):
    """Result of matching a planted fact against agent claims."""

    planted_fact_id: str
    matched_claim_id: str | None = None
    match_strategy_used: MatchStrategy
    match_score: float = Field(..., ge=0.0)
    matched_claim_confidence: float | None = None
    matched_claim_text: str | None = None
    notes: str | None = None


class RiskMatch(BaseModel):
    """Result of matching a planted risk against agent risk flags."""

    planted_risk_id: str
    matched_flag_index: int | None = None
    matched_category: RiskCategory | None = None
    severity_match: bool
    notes: str | None = None


class CalibrationBucket(BaseModel):
    """One bin of confidence calibration data."""

    range_low: float = Field(..., ge=0.0, lt=1.0)
    range_high: float = Field(..., gt=0.0, le=1.0)
    claim_count: int = Field(..., ge=0)
    matched_count: int = Field(..., ge=0)
    observed_precision: float | None = None

    @model_validator(mode="after")
    def matched_count_lte_claim_count(self) -> CalibrationBucket:
        if self.matched_count > self.claim_count:
            raise ValueError("matched_count must be <= claim_count")
        return self

    @model_validator(mode="after")
    def observed_precision_set_when_claims_exist(self) -> CalibrationBucket:
        if self.claim_count > 0 and self.observed_precision is None:
            raise ValueError("observed_precision is required when claim_count > 0")
        return self


class RunArtifacts(BaseModel):
    """Artifacts produced by a single persona run."""

    persona_id: str
    run_id: str
    agent_run_dir: Path
    report_json: Path
    audit_json: Path
    graph_export: Path | None = None
    match_cache: Path | None = None
    cost_dollars: float = Field(..., ge=0.0)
    duration_seconds: float = Field(..., ge=0.0)
    iterations_used: int = Field(..., ge=0)
    search_calls_used: int = Field(..., ge=0)
    exit_code: int

    @field_validator("agent_run_dir", "report_json", "audit_json")
    @classmethod
    def paths_must_exist(cls, v: Path | None) -> Path | None:
        if v is not None and not v.exists():
            # We allow non-existent paths during initial construction
            # because the runner creates them. Validation happens at use time.
            pass
        return v


class PersonaMetrics(BaseModel):
    """All metrics for a single persona."""

    persona_id: str
    recall_by_tier: dict[Tier, float]
    found_by_tier: dict[Tier, int] = Field(default_factory=dict)
    total_by_tier: dict[Tier, int] = Field(default_factory=dict)
    precision: float = Field(..., ge=0.0, le=1.0)
    precision_sample_size: int
    precision_is_automated: bool
    risk_recall: float = Field(..., ge=0.0, le=1.0)
    fact_matches: list[FactMatch]
    risk_matches: list[RiskMatch]
    calibration_buckets: list[CalibrationBucket] = Field(..., min_length=5, max_length=5)
    expected_calibration_error: float = Field(..., ge=0.0, le=1.0)
    cost_dollars: float = Field(..., ge=0.0)
    duration_seconds: float = Field(..., ge=0.0)
    iterations_used: int = Field(default=0, ge=0)
    search_calls_used: int = Field(default=0, ge=0)
    success_criteria: dict[str, bool]


class MetricsReport(BaseModel):
    """Combined metrics report across all personas in a run."""

    run_id: str
    timestamp: datetime
    per_persona: list[PersonaMetrics]
    overall_pass: bool
    total_cost_dollars: float = Field(..., ge=0.0)
    total_duration_seconds: float = Field(..., ge=0.0)
