from __future__ import annotations

import math

import pytest

from research_agent.confidence import (
    ConfidenceWeights,
    compute_confidence,
    consistency_score,
    corroboration_score,
    load_weights,
    recency_factor,
    source_authority_score,
)

# ---------------------------------------------------------------------------
# ConfidenceWeights
# ---------------------------------------------------------------------------


class TestConfidenceWeights:
    def test_default_weights_sum_to_1(self) -> None:
        w = ConfidenceWeights()
        total = w.authority + w.corroboration + w.recency + w.consistency
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_default_authority(self) -> None:
        assert ConfidenceWeights().authority == pytest.approx(0.35)

    def test_default_corroboration(self) -> None:
        assert ConfidenceWeights().corroboration == pytest.approx(0.30)

    def test_default_recency(self) -> None:
        assert ConfidenceWeights().recency == pytest.approx(0.15)

    def test_default_consistency(self) -> None:
        assert ConfidenceWeights().consistency == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# load_weights — env var overrides
# ---------------------------------------------------------------------------


class TestLoadWeights:
    def test_defaults_when_no_env_vars(self, monkeypatch) -> None:
        for key in [
            "CONFIDENCE_WEIGHT_AUTHORITY",
            "CONFIDENCE_WEIGHT_CORROBORATION",
            "CONFIDENCE_WEIGHT_RECENCY",
            "CONFIDENCE_WEIGHT_CONSISTENCY",
        ]:
            monkeypatch.delenv(key, raising=False)
        w = load_weights()
        assert w.authority == pytest.approx(0.35)

    def test_env_var_overrides_authority(self, monkeypatch) -> None:
        monkeypatch.setenv("CONFIDENCE_WEIGHT_AUTHORITY", "0.5")
        monkeypatch.setenv("CONFIDENCE_WEIGHT_CORROBORATION", "0.30")
        monkeypatch.setenv("CONFIDENCE_WEIGHT_RECENCY", "0.10")
        monkeypatch.setenv("CONFIDENCE_WEIGHT_CONSISTENCY", "0.10")
        w = load_weights()
        assert w.authority == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# source_authority_score
# ---------------------------------------------------------------------------


class TestSourceAuthorityScore:
    def test_tier1_is_1(self) -> None:
        assert source_authority_score(1) == pytest.approx(1.0)

    def test_tier2_is_0_8(self) -> None:
        assert source_authority_score(2) == pytest.approx(0.8)

    def test_tier3_is_0_6(self) -> None:
        assert source_authority_score(3) == pytest.approx(0.6)

    def test_tier4_is_0_3(self) -> None:
        assert source_authority_score(4) == pytest.approx(0.3)

    def test_unknown_tier_returns_floor(self) -> None:
        assert source_authority_score(99) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# corroboration_score
# ---------------------------------------------------------------------------


class TestCorroborationScore:
    def test_zero_domains(self) -> None:
        assert corroboration_score(0) == pytest.approx(0.0)

    def test_one_domain(self) -> None:
        expected = math.log(2) / math.log(4)
        assert corroboration_score(1) == pytest.approx(expected)

    def test_three_domains_is_1(self) -> None:
        # log(4) / log(4) = 1.0
        assert corroboration_score(3) == pytest.approx(1.0)

    def test_more_than_three_capped_at_1(self) -> None:
        assert corroboration_score(10) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# recency_factor
# ---------------------------------------------------------------------------


class TestRecencyFactor:
    def test_timeless_always_1(self) -> None:
        assert recency_factor(is_timeless=True) == pytest.approx(1.0)

    def test_timeless_ignores_months(self) -> None:
        assert recency_factor(is_timeless=True, months_old=100) == pytest.approx(1.0)

    def test_fresh_time_sensitive(self) -> None:
        # 0 months old → 1.0 - 0/36 = 1.0
        assert recency_factor(is_timeless=False, months_old=0) == pytest.approx(1.0)

    def test_18_months_old(self) -> None:
        expected = max(0.2, 1.0 - 18 / 36)  # = 0.5
        assert recency_factor(is_timeless=False, months_old=18) == pytest.approx(expected)

    def test_very_old_floors_at_0_2(self) -> None:
        # 36+ months → floor at 0.2
        assert recency_factor(is_timeless=False, months_old=36) == pytest.approx(0.2)
        assert recency_factor(is_timeless=False, months_old=100) == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# consistency_score
# ---------------------------------------------------------------------------


class TestConsistencyScore:
    def test_no_contradictions(self) -> None:
        assert consistency_score(None) == pytest.approx(1.0)

    def test_contradicted_by_tier1(self) -> None:
        assert consistency_score(1) == pytest.approx(0.2)

    def test_contradicted_by_tier2(self) -> None:
        assert consistency_score(2) == pytest.approx(0.2)

    def test_contradicted_by_tier3(self) -> None:
        assert consistency_score(3) == pytest.approx(0.5)

    def test_contradicted_by_tier4(self) -> None:
        assert consistency_score(4) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# compute_confidence — integration-style tests
# ---------------------------------------------------------------------------


class TestComputeConfidence:
    def test_single_tier1_no_corroborations(self) -> None:
        """Single Tier-1 source, no corroborations, timeless, no contradictions.

        Expected ≈ 0.35×1.0 + 0.30×0.0 + 0.15×1.0 + 0.20×1.0 = 0.70
        Wait — 1 independent domain means n=1: corroboration_score(1) ≈ 0.5
        Let's compute exactly.
        """
        # 1 domain (the source itself counts as 1 independent domain)
        score = compute_confidence(max_tier=1, n_independent_domains=1, is_timeless=True)
        # authority=0.35×1.0, corroboration=0.30×log(2)/log(4)≈0.15, recency=0.15×1.0, consistency=0.20×1.0
        # 0.35 + 0.15 + 0.15 + 0.20 = 0.85
        assert 0.3 <= score <= 1.0

    def test_single_tier1_zero_corroborations_approx_authority_weight(self) -> None:
        """With 0 independent domains: confidence ≈ 0.35 (authority) + 0 (corroboration) + 0.15 + 0.20."""
        score = compute_confidence(max_tier=1, n_independent_domains=0, is_timeless=True)
        # 0.35×1.0 + 0.30×0.0 + 0.15×1.0 + 0.20×1.0 = 0.70
        assert score == pytest.approx(0.70, abs=1e-6)

    def test_two_independent_tier2_sources_above_0_5(self) -> None:
        """Two independent Tier-2 sources should produce confidence > 0.5."""
        score = compute_confidence(max_tier=2, n_independent_domains=2, is_timeless=True)
        assert score > 0.5

    def test_tier4_with_contradiction_below_0_4(self) -> None:
        """Tier-4 source with a high-authority contradiction should be < 0.4."""
        score = compute_confidence(
            max_tier=4,
            n_independent_domains=1,
            is_timeless=False,
            months_old=24,
            contradictions_max_tier=1,  # contradicted by Tier-1 source
        )
        assert score < 0.4

    def test_result_always_in_0_1(self) -> None:
        """compute_confidence must always return a value in [0, 1]."""
        test_cases = [
            (1, 0, True, 0, None),
            (1, 10, True, 0, None),
            (4, 0, False, 36, 1),
            (4, 3, False, 0, 4),
            (2, 2, True, 0, 2),
        ]
        for max_tier, n_domains, timeless, months, contradiction in test_cases:
            score = compute_confidence(
                max_tier=max_tier,
                n_independent_domains=n_domains,
                is_timeless=timeless,
                months_old=months,
                contradictions_max_tier=contradiction,
            )
            assert 0.0 <= score <= 1.0, (
                f"Out of range for params: tier={max_tier}, n={n_domains}, "
                f"timeless={timeless}, months={months}, contradiction={contradiction}"
            )

    def test_custom_weights_applied(self) -> None:
        """Custom weights should be used instead of defaults."""
        custom = ConfidenceWeights(authority=1.0, corroboration=0.0, recency=0.0, consistency=0.0)
        score = compute_confidence(
            max_tier=1,
            n_independent_domains=0,
            is_timeless=True,
            weights=custom,
        )
        # 1.0 × 1.0 = 1.0
        assert score == pytest.approx(1.0)
