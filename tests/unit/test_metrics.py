"""Unit tests for eval/metrics.py."""

from __future__ import annotations

import pytest
from eval.metrics import (
    EvalMetrics,
    compute_precision,
    compute_recall,
    compute_risk_recall,
)

# ---------------------------------------------------------------------------
# compute_recall
# ---------------------------------------------------------------------------


class TestComputeRecall:
    def test_no_match_returns_zero_found(self) -> None:
        """Returns (0, n) when validated claims share no keywords with ground truth."""
        ground_truth = [
            {"subject": "Alice", "predicate": "works at", "object": "Acme Corp"},
            {"subject": "Alice", "predicate": "holds degree from", "object": "MIT"},
        ]
        validated_claims: list[dict] = [
            {"subject": "Bob", "predicate": "lives in", "object": "Paris"},
        ]
        found, total = compute_recall(ground_truth, validated_claims)
        assert found == 0
        assert total == 2

    def test_exact_match_all_found(self) -> None:
        """All ground truth items are found when claims contain identical text."""
        ground_truth = [
            {
                "subject": "Alexandra Chen",
                "predicate": "serves as",
                "object": "CEO of Meridian Capital Partners",
            },
        ]
        validated_claims = [
            {
                "subject": "Alexandra Chen",
                "predicate": "serves as",
                "object": "CEO of Meridian Capital Partners",
                "confidence": 0.9,
                "supporting_sources": ["https://a.example", "https://b.example"],
            }
        ]
        found, total = compute_recall(ground_truth, validated_claims)
        assert found == 1
        assert total == 1

    def test_partial_keyword_overlap_matches_above_threshold(self) -> None:
        """A claim that shares enough keywords with GT is counted as a match."""
        ground_truth = [
            {
                "subject": "Marcus Okonkwo",
                "predicate": "co-founded",
                "object": "Okonkwo Energy Holdings 2008",
            }
        ]
        # Claim text shares most of the GT words
        validated_claims = [
            {
                "subject": "Marcus Okonkwo",
                "predicate": "co-founded",
                "object": "Okonkwo Energy Holdings in 2008",
                "confidence": 0.8,
                "supporting_sources": ["https://source.example"],
            }
        ]
        found, total = compute_recall(ground_truth, validated_claims, match_threshold=0.6)
        assert found == 1
        assert total == 1

    def test_empty_ground_truth_returns_zero_total(self) -> None:
        """With no ground truth entries, total is 0 and found is 0."""
        found, total = compute_recall([], [{"subject": "X", "predicate": "Y", "object": "Z"}])
        assert found == 0
        assert total == 0

    def test_empty_claims_returns_zero_found(self) -> None:
        """With ground truth but no claims, nothing is found."""
        ground_truth = [{"subject": "A", "predicate": "B", "object": "C"}]
        found, total = compute_recall(ground_truth, [])
        assert found == 0
        assert total == 1

    def test_each_gt_counted_at_most_once(self) -> None:
        """A single GT item is not double-counted even if multiple claims match."""
        ground_truth = [
            {"subject": "Alexandra Chen", "predicate": "holds degree", "object": "MBA INSEAD 2009"}
        ]
        validated_claims = [
            {
                "subject": "Alexandra Chen",
                "predicate": "holds degree",
                "object": "MBA INSEAD 2009",
                "confidence": 0.9,
                "supporting_sources": [],
            },
            {
                "subject": "Alexandra Chen",
                "predicate": "holds degree",
                "object": "MBA INSEAD 2009",
                "confidence": 0.85,
                "supporting_sources": [],
            },
        ]
        found, total = compute_recall(ground_truth, validated_claims)
        assert found == 1
        assert total == 1


# ---------------------------------------------------------------------------
# compute_precision
# ---------------------------------------------------------------------------


class TestComputePrecision:
    def test_empty_claims_returns_one(self) -> None:
        """Precision is 1.0 when there are no claims (vacuously true)."""
        assert compute_precision([]) == 1.0

    def test_all_high_confidence_returns_one(self) -> None:
        """All claims with confidence > 0.5 yields precision = 1.0."""
        claims = [
            {"confidence": 0.9, "supporting_sources": []},
            {"confidence": 0.75, "supporting_sources": []},
            {"confidence": 0.6, "supporting_sources": []},
        ]
        assert compute_precision(claims) == 1.0

    def test_all_low_confidence_returns_zero(self) -> None:
        """All claims with confidence ≤ 0.5 yields precision = 0.0."""
        claims = [
            {"confidence": 0.4, "supporting_sources": []},
            {"confidence": 0.3, "supporting_sources": []},
        ]
        assert compute_precision(claims) == 0.0

    def test_mixed_confidence_returns_correct_fraction(self) -> None:
        """Half high-confidence claims yields precision = 0.5."""
        claims = [
            {"confidence": 0.8, "supporting_sources": []},  # > 0.5
            {"confidence": 0.2, "supporting_sources": []},  # ≤ 0.5
        ]
        result = compute_precision(claims)
        assert result == pytest.approx(0.5)

    def test_sample_size_limits_evaluation(self) -> None:
        """Only the first sample_size claims are evaluated."""
        # First 2 are low confidence, rest are high — sample_size=2 should give 0.0
        claims = [
            {"confidence": 0.1},
            {"confidence": 0.2},
            {"confidence": 0.9},
            {"confidence": 0.9},
        ]
        result = compute_precision(claims, sample_size=2)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_risk_recall
# ---------------------------------------------------------------------------


class TestComputeRiskRecall:
    def test_exact_type_and_keyword_match(self) -> None:
        """A flag matching both type and description keywords is counted."""
        expected = [{"type": "REGULATORY", "description": "MAS Enforcement Inquiry 2021"}]
        actual = [{"type": "REGULATORY", "description": "MAS Enforcement Inquiry resolved 2021"}]
        found, total = compute_risk_recall(expected, actual)
        assert found == 1
        assert total == 1

    def test_type_mismatch_not_counted(self) -> None:
        """A flag with matching description but wrong type is not counted."""
        expected = [{"type": "REGULATORY", "description": "MAS Enforcement Inquiry 2021"}]
        actual = [{"type": "NETWORK", "description": "MAS Enforcement Inquiry 2021"}]
        found, total = compute_risk_recall(expected, actual)
        assert found == 0
        assert total == 1

    def test_no_actual_flags_returns_zero(self) -> None:
        """Returns (0, n) when no actual flags are provided."""
        expected = [
            {"type": "REGULATORY", "description": "OFAC screening"},
            {"type": "NETWORK", "description": "Sanctioned individual link"},
        ]
        found, total = compute_risk_recall(expected, [])
        assert found == 0
        assert total == 2

    def test_empty_expected_returns_zero_total(self) -> None:
        """Returns (0, 0) when expected flags list is empty."""
        actual = [{"type": "REGULATORY", "description": "Some issue"}]
        found, total = compute_risk_recall([], actual)
        assert found == 0
        assert total == 0

    def test_multiple_flags_partially_matched(self) -> None:
        """Only matched flags are counted; unmatched expected flags reduce recall."""
        expected = [
            {"type": "REGULATORY", "description": "MAS inquiry resolved"},
            {"type": "NETWORK", "description": "Hartwell Group fund connection"},
        ]
        actual = [
            {"type": "REGULATORY", "description": "MAS enforcement inquiry resolved 2021"},
            # NETWORK flag is absent
        ]
        found, total = compute_risk_recall(expected, actual)
        assert found == 1
        assert total == 2

    def test_low_keyword_overlap_not_counted(self) -> None:
        """A flag whose description shares too few keywords is not counted."""
        expected = [{"type": "REGULATORY", "description": "OFAC sanctions screening cleared"}]
        actual = [
            # Only 1 overlapping word out of 4 expected words => overlap < 0.5
            {"type": "REGULATORY", "description": "completely unrelated matter resolved"}
        ]
        found, total = compute_risk_recall(expected, actual, match_threshold=0.5)
        assert found == 0
        assert total == 1


# ---------------------------------------------------------------------------
# EvalMetrics.pass_fail
# ---------------------------------------------------------------------------


class TestEvalMetricsPassFail:
    def _make_metrics(self, **kwargs: float) -> EvalMetrics:
        defaults = {
            "recall_easy": 0.75,
            "recall_medium": 0.55,
            "recall_hard": 0.35,
            "precision": 0.92,
            "confidence_calibration": 0.96,
            "risk_recall": 0.85,
        }
        defaults.update(kwargs)
        return EvalMetrics(persona_name="test", **defaults)  # type: ignore[arg-type]

    def _default_thresholds(self) -> dict[str, float]:
        return {
            "recall_easy": 0.70,
            "recall_medium": 0.50,
            "precision": 0.90,
            "confidence_calibration": 0.95,
            "risk_recall": 0.80,
        }

    def test_all_pass_when_above_thresholds(self) -> None:
        metrics = self._make_metrics()
        result = metrics.pass_fail(self._default_thresholds())
        assert all(result.values()), f"Expected all pass, got: {result}"

    def test_overall_pass_true_when_all_pass(self) -> None:
        metrics = self._make_metrics()
        assert metrics.overall_pass(self._default_thresholds()) is True

    def test_recall_easy_fails_when_below_threshold(self) -> None:
        metrics = self._make_metrics(recall_easy=0.60)
        result = metrics.pass_fail(self._default_thresholds())
        assert result["recall_easy"] is False

    def test_precision_fails_when_below_threshold(self) -> None:
        metrics = self._make_metrics(precision=0.85)
        result = metrics.pass_fail(self._default_thresholds())
        assert result["precision"] is False

    def test_risk_recall_fails_when_below_threshold(self) -> None:
        metrics = self._make_metrics(risk_recall=0.70)
        result = metrics.pass_fail(self._default_thresholds())
        assert result["risk_recall"] is False

    def test_overall_pass_false_when_any_fail(self) -> None:
        metrics = self._make_metrics(precision=0.80)  # below 0.90 threshold
        assert metrics.overall_pass(self._default_thresholds()) is False

    def test_boundary_value_exactly_at_threshold_passes(self) -> None:
        """A metric exactly at threshold should pass (>=)."""
        metrics = self._make_metrics(recall_easy=0.70, precision=0.90, risk_recall=0.80)
        result = metrics.pass_fail(self._default_thresholds())
        assert result["recall_easy"] is True
        assert result["precision"] is True
        assert result["risk_recall"] is True

    def test_custom_thresholds_override_defaults(self) -> None:
        """Pass custom thresholds; default values should not be used."""
        metrics = self._make_metrics(recall_easy=0.50)
        tight_thresholds = {"recall_easy": 0.40}  # easier threshold
        result = metrics.pass_fail(tight_thresholds)
        assert result["recall_easy"] is True  # 0.50 >= 0.40
