"""Claim-to-fact matching strategies for the eval suite.

Provides exact, fuzzy (rapidfuzz), and semantic (OpenAI embeddings) matching
with per-fact configurable thresholds. Claim text is constructed as
"{subject} {predicate} {object}" for comparison against planted fact
statements.
"""

from __future__ import annotations

import math
import string
from typing import Any, Protocol

import structlog

from eval.schemas import (
    FactMatch,
    MatchStrategy,
    PersonaDefinition,
    RiskMatch,
)
from research_agent.schemas import RiskFlag, ValidatedClaim

logger = structlog.get_logger()


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation."""
    return text.lower().translate(str.maketrans("", "", string.punctuation)).strip()


def exact_match(claim_text: str, fact_statement: str) -> float:
    """Return 1.0 if normalized strings are equal, else 0.0."""
    return 1.0 if _normalize(claim_text) == _normalize(fact_statement) else 0.0


def fuzzy_match(claim_text: str, fact_statement: str) -> float:
    """Return rapidfuzz partial_ratio score [0, 100]."""
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:
        raise RuntimeError("rapidfuzz is required for fuzzy matching") from exc

    return float(fuzz.partial_ratio(_normalize(claim_text), _normalize(fact_statement)))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_match(
    claim_text: str,
    fact_statement: str,
    embedder: EmbedderProtocol,
) -> float:
    """Return cosine similarity of embeddings [0.0, 1.0]."""
    claim_vec = embedder.embed(claim_text)
    fact_vec = embedder.embed(fact_statement)
    return cosine_similarity(claim_vec, fact_vec)


class EmbedderProtocol(Protocol):
    """Protocol for embedding providers."""

    def embed(self, text: str) -> list[float]:
        ...


class OpenAIEmbedder:
    """Embedder using OpenAI text-embedding-3-small."""

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model
        self._client: Any | None = None
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        if text in self._cache:
            return self._cache[text]

        if self._client is None:
            import openai

            self._client = openai.OpenAI()

        response = self._client.embeddings.create(
            model=self.model,
            input=[text],
        )
        vec = response.data[0].embedding
        self._cache[text] = vec
        return vec

    def get_cache(self) -> dict[str, list[float]]:
        """Return the embedding cache for persistence."""
        return dict(self._cache)


def _claim_text(claim: ValidatedClaim) -> str:
    """Construct comparison text from a claim."""
    return f"{claim.subject} {claim.predicate} {claim.object}".strip()


def match_facts(
    persona: PersonaDefinition,
    claims: list[ValidatedClaim],
    embedder: EmbedderProtocol | None = None,
) -> list[FactMatch]:
    """Match planted facts against agent claims using per-fact strategy.

    Returns one FactMatch per planted fact.
    """
    matches: list[FactMatch] = []

    for fact in persona.planted_facts:
        best_match: FactMatch | None = None
        effective_strategy = fact.match_strategy

        if fact.match_strategy == MatchStrategy.semantic and embedder is None:
            logger.warning(
                "semantic_fallback_to_fuzzy",
                fact_id=fact.id,
                msg="Embedder unavailable; falling back to fuzzy matching",
            )
            effective_strategy = MatchStrategy.fuzzy

        for claim in claims:
            claim_text = _claim_text(claim)
            score: float

            if effective_strategy == MatchStrategy.exact:
                score = exact_match(claim_text, fact.statement)
                threshold = fact.match_threshold / 100.0
            elif effective_strategy == MatchStrategy.fuzzy:
                score = fuzzy_match(claim_text, fact.statement)
                threshold = fact.match_threshold if fact.match_strategy == MatchStrategy.fuzzy else 80.0
            elif effective_strategy == MatchStrategy.semantic:
                assert embedder is not None
                score = semantic_match(claim_text, fact.statement, embedder)
                threshold = fact.match_threshold
            else:
                raise ValueError(f"unknown match strategy: {effective_strategy}")

            is_match = score >= threshold

            if is_match and (
                best_match is None
                or (best_match.matched_claim_confidence or 0) < claim.confidence
            ):
                best_match = FactMatch(
                    planted_fact_id=fact.id,
                    matched_claim_id=claim.id,
                    match_strategy_used=effective_strategy,
                    match_score=score,
                    matched_claim_confidence=claim.confidence,
                    matched_claim_text=claim_text,
                )

        if best_match is None:
            best_match = FactMatch(
                planted_fact_id=fact.id,
                matched_claim_id=None,
                match_strategy_used=effective_strategy,
                match_score=0.0,
                matched_claim_confidence=None,
                matched_claim_text=None,
                notes="No matching claim found",
            )

        matches.append(best_match)

    return matches


def match_risks(
    persona: PersonaDefinition,
    flags: list[RiskFlag],
) -> list[RiskMatch]:
    """Match planted risks against agent risk flags.

    Matching logic:
    - Category must match exactly.
    - Description is compared via fuzzy partial_ratio >= 60.
    - Severity match is recorded separately.
    """
    matches: list[RiskMatch] = []

    for planted in persona.planted_risks:
        best_match: RiskMatch | None = None
        best_score = 0.0

        for idx, flag in enumerate(flags):
            if flag.type != planted.risk_category:
                continue

            score = fuzzy_match(flag.description, planted.description)
            if score >= 60.0 and score > best_score:
                best_score = score
                best_match = RiskMatch(
                    planted_risk_id=planted.id,
                    matched_flag_index=idx,
                    matched_category=flag.type,
                    severity_match=(flag.severity == planted.expected_severity),
                    notes=f"Fuzzy score {score:.1f}",
                )

        if best_match is None:
            best_match = RiskMatch(
                planted_risk_id=planted.id,
                matched_flag_index=None,
                matched_category=None,
                severity_match=False,
                notes="No matching risk flag found",
            )

        matches.append(best_match)

    return matches
