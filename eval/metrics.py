"""Metric computation for the eval suite.

Functions:
- compute_recall: recall by tier
- compute_precision: automated precision for synthetic, sample for real_public
- compute_calibration: ECE with 5 equal-width bins
- compute_risk_recall: fraction of planted risks found
- cost_summary: aggregate cost/duration from artifacts
- evaluate_success_criteria: pass/fail against thresholds
"""

from __future__ import annotations

import random
from typing import Any

import structlog

from eval.matcher import fuzzy_match
from eval.schemas import (
    CalibrationBucket,
    FactMatch,
    PersonaMetrics,
    PersonaType,
    RiskMatch,
    RunArtifacts,
    Tier,
)
from research_agent.schemas import ValidatedClaim

logger = structlog.get_logger()

# Fixed bins for ECE: (0.0, 0.2], (0.2, 0.4], (0.4, 0.6], (0.6, 0.8], (0.8, 1.0]
_CALIBRATION_BINS = [
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
]


def compute_recall(
    fact_matches: list[FactMatch],
    planted_facts: list[Any],
) -> dict[Tier, float]:
    """Compute recall per tier.

    Returns dict with keys easy, medium, hard.
    """
    tier_totals: dict[Tier, int] = {Tier.easy: 0, Tier.medium: 0, Tier.hard: 0}
    tier_found: dict[Tier, int] = {Tier.easy: 0, Tier.medium: 0, Tier.hard: 0}

    # Build a map from fact id to tier for lookups
    fact_tiers = {f.id: f.difficulty for f in planted_facts}

    for match in fact_matches:
        tier = fact_tiers.get(match.planted_fact_id)
        if tier is None:
            continue
        tier_totals[tier] += 1
        if match.matched_claim_id is not None:
            tier_found[tier] += 1

    return {
        Tier.easy: tier_found[Tier.easy] / max(tier_totals[Tier.easy], 1),
        Tier.medium: tier_found[Tier.medium] / max(tier_totals[Tier.medium], 1),
        Tier.hard: tier_found[Tier.hard] / max(tier_totals[Tier.hard], 1),
    }


def compute_precision(
    claims: list[ValidatedClaim],
    planted_facts: list[Any],
    persona_type: PersonaType,
    sample_size: int = 30,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute precision metrics.

    For synthetic personas: automated check using fuzzy matching against
    all planted facts. For real_public: sample claims for manual review.

    Returns dict with keys:
    - rate: float | None
    - sampled_claims: list[dict]
    - is_automated: bool
    """
    if not claims:
        return {
            "rate": 0.0,
            "sampled_claims": [],
            "is_automated": True,
        }

    if persona_type == PersonaType.synthetic:
        # Automated: check ALL claims against planted facts (full ground truth)
        correct = 0
        sampled_claims: list[dict[str, Any]] = []

        for claim in claims:
            claim_text = f"{claim.subject} {claim.predicate} {claim.object}"
            is_correct = False
            best_score = 0.0
            for fact in planted_facts:
                score = fuzzy_match(claim_text, fact.statement)
                if score > best_score:
                    best_score = score
                if score >= 60.0:
                    is_correct = True
                    break

            if is_correct:
                correct += 1

            sampled_claims.append({
                "claim_id": claim.id,
                "claim_text": claim_text,
                "confidence": claim.confidence,
                "is_correct": is_correct,
                "best_fuzzy_score": best_score,
            })

        return {
            "rate": correct / len(claims),
            "sampled_claims": sampled_claims,
            "is_automated": True,
        }

    # real_public: sample for manual review
    rng = random.Random(seed)
    sample = rng.sample(claims, min(sample_size, len(claims)))
    sampled_claims = [
        {
            "claim_id": claim.id,
            "claim_text": f"{claim.subject} {claim.predicate} {claim.object}",
            "confidence": claim.confidence,
            "is_correct": None,  # to be labeled manually
        }
        for claim in sample
    ]

    return {
        "rate": None,
        "sampled_claims": sampled_claims,
        "is_automated": False,
    }


def compute_calibration(
    claims: list[ValidatedClaim],
    fact_matches: list[FactMatch],
) -> tuple[list[CalibrationBucket], float]:
    """Compute ECE with 5 equal-width bins.

    Returns (buckets, ece).
    """
    matched_claim_ids = {m.matched_claim_id for m in fact_matches if m.matched_claim_id}

    buckets: list[CalibrationBucket] = []
    ece = 0.0
    total_claims = len(claims)

    for idx, (low, high) in enumerate(_CALIBRATION_BINS):
        if idx == 0:
            bin_claims = [c for c in claims if low <= c.confidence <= high]
        else:
            bin_claims = [c for c in claims if low < c.confidence <= high]
        claim_count = len(bin_claims)
        matched_count = sum(1 for c in bin_claims if c.id in matched_claim_ids)

        observed = None
        if claim_count > 0:
            observed = matched_count / claim_count
            mean_confidence = sum(c.confidence for c in bin_claims) / claim_count
            ece += (claim_count / max(total_claims, 1)) * abs(observed - mean_confidence)

        buckets.append(
            CalibrationBucket(
                range_low=low,
                range_high=high,
                claim_count=claim_count,
                matched_count=matched_count,
                observed_precision=observed,
            )
        )

    return buckets, ece


def compute_risk_recall(
    risk_matches: list[RiskMatch],
    planted_risks: list[Any],
) -> float:
    """Compute fraction of planted risks that were matched."""
    if not planted_risks:
        return 1.0
    found = sum(1 for m in risk_matches if m.matched_flag_index is not None)
    return found / len(planted_risks)


def cost_summary(artifacts: RunArtifacts) -> dict[str, Any]:
    """Extract cost/duration summary from run artifacts."""
    return {
        "cost_dollars": artifacts.cost_dollars,
        "duration_seconds": artifacts.duration_seconds,
        "iterations_used": artifacts.iterations_used,
        "search_calls_used": artifacts.search_calls_used,
    }


def evaluate_success_criteria(metrics: PersonaMetrics) -> dict[str, bool]:
    """Evaluate pass/fail for each success criterion.

    Criteria:
    - high_confidence_precision: (0.8, 1.0] bucket claims >= 95% precision
    - easy_recall: >= 80%
    - risk_recall: 100%
    """
    # Find the (0.8, 1.0] bucket
    high_conf_bucket = None
    for bucket in metrics.calibration_buckets:
        if bucket.range_low == 0.8 and bucket.range_high == 1.0:
            high_conf_bucket = bucket
            break

    if high_conf_bucket and high_conf_bucket.claim_count > 0:
        high_conf_precision = high_conf_bucket.observed_precision or 0.0
    else:
        high_conf_precision = 1.0  # vacuously true if no high-confidence claims

    return {
        "high_confidence_precision": high_conf_precision >= 0.95,
        "easy_recall": metrics.recall_by_tier.get(Tier.easy, 0.0) >= 0.80,
        "risk_recall": metrics.risk_recall >= 1.0,
    }
