from __future__ import annotations

import math
import os
from dataclasses import dataclass


@dataclass
class ConfidenceWeights:
    """Weights for the four factors of the confidence formula.

    Defaults sum to 1.0: authority=0.35, corroboration=0.30, recency=0.15, consistency=0.20.
    Can be overridden via environment variables.
    """

    authority: float = 0.35
    corroboration: float = 0.30
    recency: float = 0.15
    consistency: float = 0.20


def load_weights() -> ConfidenceWeights:
    """Load confidence weights from env vars, falling back to defaults."""
    defaults = ConfidenceWeights()
    authority = float(os.environ.get("CONFIDENCE_WEIGHT_AUTHORITY", defaults.authority))
    corroboration = float(os.environ.get("CONFIDENCE_WEIGHT_CORROBORATION", defaults.corroboration))
    recency = float(os.environ.get("CONFIDENCE_WEIGHT_RECENCY", defaults.recency))
    consistency = float(os.environ.get("CONFIDENCE_WEIGHT_CONSISTENCY", defaults.consistency))
    return ConfidenceWeights(
        authority=authority,
        corroboration=corroboration,
        recency=recency,
        consistency=consistency,
    )


# Mapping from source tier (1-4) to authority score.
TIER_SCORES: dict[int, float] = {
    1: 1.0,  # gov, court, SEC — highest authority
    2: 0.8,  # major news, official sites
    3: 0.6,  # industry, LinkedIn, professional bios
    4: 0.3,  # blogs, social media, forums
}


def source_authority_score(max_tier: int) -> float:
    """Return the authority score for the best (lowest-numbered) source tier seen.

    Args:
        max_tier: The numerically smallest (highest authority) tier among sources.
                  Valid values are 1-4. Out-of-range values clamp to 0.3 (floor).
    """
    return TIER_SCORES.get(max_tier, 0.3)


def corroboration_score(n_independent_domains: int) -> float:
    """Return normalized log corroboration score.

    Uses the formula: min(log(n+1) / log(4), 1.0)
    So 3 independent domains yields 1.0 (since log(4)/log(4) = 1.0).

    Args:
        n_independent_domains: Number of independent registrable domains corroborating the claim.
    """
    if n_independent_domains <= 0:
        return 0.0
    return min(math.log(n_independent_domains + 1) / math.log(4), 1.0)


def recency_factor(is_timeless: bool, months_old: int = 0) -> float:
    """Return the recency component of confidence.

    Timeless claims (education, birth) always return 1.0.
    Time-sensitive claims decay: max(0.2, 1.0 - (months_old / 36)).

    Args:
        is_timeless: True for claims that do not expire (e.g., birth year, degree).
        months_old: How many months since the claim was last verified (used only when
                    is_timeless is False).
    """
    if is_timeless:
        return 1.0
    return max(0.2, 1.0 - (months_old / 36))


def consistency_score(contradictions_max_tier: int | None) -> float:
    """Return consistency component based on whether the claim is contradicted.

    Args:
        contradictions_max_tier: None if no contradictions. Otherwise, the numerically
            smallest (highest authority) tier of any contradicting source.
            - None  → 1.0 (no contradictions)
            - equal to the supporting source tier → 0.5
            - lower number (higher authority) than supporting sources → 0.2
    """
    if contradictions_max_tier is None:
        return 1.0
    # Any contradiction at tier 1 or 2 (high authority) → 0.2
    if contradictions_max_tier <= 2:
        return 0.2
    # Contradiction at lower authority tiers → 0.5
    return 0.5


def compute_confidence(
    max_tier: int,
    n_independent_domains: int,
    is_timeless: bool = True,
    months_old: int = 0,
    contradictions_max_tier: int | None = None,
    weights: ConfidenceWeights | None = None,
) -> float:
    """Compute claim confidence using the 4-factor weighted formula.

    confidence = W_authority × source_authority_score(max_tier)
               + W_corroboration × corroboration_score(n_independent_domains)
               + W_recency × recency_factor(is_timeless, months_old)
               + W_consistency × consistency_score(contradictions_max_tier)

    Args:
        max_tier: Best (lowest-number) source tier (1=gov/court, 4=blog).
        n_independent_domains: Number of independent domains corroborating the claim.
        is_timeless: Whether the claim is timeless (no decay).
        months_old: Months since last verification (for time-sensitive claims).
        contradictions_max_tier: Tier of the strongest contradicting source, or None.
        weights: Override default weights. If None, loads from env then uses defaults.

    Returns:
        Confidence score in [0.0, 1.0].
    """
    if weights is None:
        weights = load_weights()

    score = (
        weights.authority * source_authority_score(max_tier)
        + weights.corroboration * corroboration_score(n_independent_domains)
        + weights.recency * recency_factor(is_timeless, months_old)
        + weights.consistency * consistency_score(contradictions_max_tier)
    )
    # Clamp to [0, 1] for safety (floating point edge cases)
    return max(0.0, min(1.0, score))
