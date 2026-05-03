from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    EVENT = "EVENT"


class TargetProfile(BaseModel):
    name: str  # max 200 chars
    aliases: list[str] = Field(default_factory=list)
    role: str | None = None
    organization: str | None = None
    context: str | None = None
    geographic_hint: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty_or_too_long(cls, v: str) -> str:
        """Validate that name is non-empty and at most 200 characters."""
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        if len(v) > 200:
            raise ValueError("name must not exceed 200 characters")
        return v


class SubQuestion(BaseModel):
    id: str  # e.g. "sq-001"
    dimension: str  # biographical, professional, financial, network, statements, risk
    question: str
    rationale: str
    answer_criteria: str
    initial_query: str
    priority: int  # 1=highest


class ResearchPlan(BaseModel):
    iteration: int
    sub_questions: list[SubQuestion]
    plan_notes: str


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    content: str | None = None
    retrieved_at: datetime
    provider: str  # "brave", "exa", "firecrawl"


class SearchTurn(BaseModel):
    iteration: int
    query: str
    provider: str
    results: list[SearchResult]


class Source(BaseModel):
    url: str
    domain: str  # registrable domain
    tier: int  # 1-4
    retrieved_at: datetime
    robots_allowed: bool


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    predicate: str
    object: str  # noqa: A003
    attributes: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str]  # ≥1 required
    extraction_confidence: float
    asserted_at: datetime | None = None

    @field_validator("source_urls")
    @classmethod
    def source_urls_must_have_at_least_one(cls, v: list[str]) -> list[str]:
        """Validate that at least one source URL is provided."""
        if not v:
            raise ValueError("source_urls must have at least 1 item")
        return v


class ValidatedClaim(Claim):
    confidence: float  # [0, 1] from confidence formula
    supporting_sources: list[Source] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)  # claim IDs
    validation_notes: str = ""


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EntityType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float


class Relation(BaseModel):
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float
    evidence_claim_ids: list[str] = Field(default_factory=list)


class RiskCategory(StrEnum):
    REGULATORY = "REGULATORY"
    REPUTATIONAL = "REPUTATIONAL"
    NETWORK = "NETWORK"
    FINANCIAL = "FINANCIAL"
    INCONSISTENCY = "INCONSISTENCY"
    COVERAGE_GAP = "COVERAGE_GAP"
    OTHER = "OTHER"


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFlag(BaseModel):
    type: RiskCategory  # noqa: A003
    severity: RiskSeverity
    description: str
    evidence_claim_ids: list[str] = Field(default_factory=list)
    confidence: float
    justification: str | None = None  # required when type == OTHER

    @model_validator(mode="after")
    def justification_required_for_other(self) -> RiskFlag:
        """Require justification when risk type is OTHER."""
        if self.type == RiskCategory.OTHER and not self.justification:
            raise ValueError("justification is required when type is OTHER")
        return self


class RetryRecord(BaseModel):
    attempt: int
    reason: str
    latency_ms: float


class AuditEntry(BaseModel):
    timestamp: datetime
    node: str
    input_state_hash: str
    prompt_filled: str
    raw_response: str
    parsed_output: dict[str, Any]
    latency_ms: float
    tokens_in: int
    tokens_out: int
    dollars: float
    retries: list[RetryRecord] = Field(default_factory=list)


class Budget(BaseModel):
    max_iterations: int = 8
    used_iterations: int = 0
    max_search_calls: int = 60
    used_search_calls: int = 0
    max_dollars: float = 5.0
    used_dollars: float = 0.0
    max_seconds_per_iteration: int = 180
    used_seconds_current_iteration: float = 0.0
    last_iteration_cost: float = 0.0

    @field_validator(
        "used_iterations",
        "used_search_calls",
        "used_dollars",
        "used_seconds_current_iteration",
        "last_iteration_cost",
    )
    @classmethod
    def used_fields_must_be_non_negative(cls, v: float) -> float:
        """Validate that all used_ fields are >= 0."""
        if v < 0:
            raise ValueError("used fields must be >= 0")
        return v
