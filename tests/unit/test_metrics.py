"""Unit tests for eval/metrics.py."""

from __future__ import annotations

from pathlib import Path

from eval.metrics import (
    compute_calibration,
    compute_precision,
    compute_recall,
    compute_risk_recall,
    cost_summary,
    evaluate_success_criteria,
)
from eval.schemas import (
    CalibrationBucket,
    FactMatch,
    MatchStrategy,
    PersonaMetrics,
    PersonaType,
    RiskMatch,
    RunArtifacts,
    Tier,
)

from research_agent.schemas import RiskCategory, RiskSeverity, ValidatedClaim


class TestComputeRecall:
    def test_three_of_four_easy(self) -> None:
        from eval.schemas import FactType, PlantedFact, ResearchDimension
        facts = [
            PlantedFact(
                id="fact_e01", statement="A", difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical, notes="n", source_urls=["u"],
            ),
            PlantedFact(
                id="fact_e02", statement="B", difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical, notes="n", source_urls=["u"],
            ),
            PlantedFact(
                id="fact_e03", statement="C", difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical, notes="n", source_urls=["u"],
            ),
            PlantedFact(
                id="fact_e04", statement="D", difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical, notes="n", source_urls=["u"],
            ),
        ]
        matches = [
            FactMatch(planted_fact_id="fact_e01", match_strategy_used=MatchStrategy.exact, match_score=1.0, matched_claim_id="c1"),
            FactMatch(planted_fact_id="fact_e02", match_strategy_used=MatchStrategy.exact, match_score=1.0, matched_claim_id="c2"),
            FactMatch(planted_fact_id="fact_e03", match_strategy_used=MatchStrategy.exact, match_score=1.0, matched_claim_id="c3"),
            FactMatch(planted_fact_id="fact_e04", match_strategy_used=MatchStrategy.exact, match_score=0.0, matched_claim_id=None),
        ]
        recall = compute_recall(matches, facts)
        assert recall[Tier.easy] == 0.75

    def test_empty(self) -> None:
        recall = compute_recall([], [])
        assert recall[Tier.easy] == 0.0
        assert recall[Tier.medium] == 0.0
        assert recall[Tier.hard] == 0.0


class TestComputePrecision:
    def test_synthetic_automated(self) -> None:
        from eval.schemas import FactType, PlantedFact, ResearchDimension
        facts = [
            PlantedFact(
                id="fact_e01", statement="Founded TestCo", difficulty=Tier.easy,
                expected_dimension=ResearchDimension.professional_history,
                fact_type=FactType.role, notes="n", source_urls=["u"],
            ),
        ]
        claims = [
            ValidatedClaim(
                subject="Person", predicate="founded", object="TestCo",
                source_urls=["u"], extraction_confidence=0.9, confidence=0.9,
            ),
            ValidatedClaim(
                subject="Person", predicate="did", object="something else",
                source_urls=["u"], extraction_confidence=0.5, confidence=0.5,
            ),
        ]
        result = compute_precision(claims, facts, PersonaType.synthetic, sample_size=10)
        assert result["is_automated"] is True
        assert result["rate"] == 0.5
        assert len(result["sampled_claims"]) == 2

    def test_real_public_manual(self) -> None:
        claims = [
            ValidatedClaim(
                subject="Person", predicate="is", object="CEO",
                source_urls=["u"], extraction_confidence=0.9, confidence=0.9,
            ),
        ]
        result = compute_precision(claims, [], PersonaType.real_public, sample_size=10)
        assert result["is_automated"] is False
        assert result["rate"] is None
        assert result["sampled_claims"][0]["is_correct"] is None

    def test_no_claims(self) -> None:
        result = compute_precision([], [], PersonaType.synthetic)
        assert result["rate"] == 0.0
        assert result["is_automated"] is True


class TestComputeCalibration:
    def test_hand_built_claims(self) -> None:
        claims = [
            ValidatedClaim(
                subject="P", predicate="p", object="o",
                source_urls=["u"], extraction_confidence=0.9, confidence=0.9,
            ),
            ValidatedClaim(
                subject="P", predicate="p", object="o2",
                source_urls=["u"], extraction_confidence=0.85, confidence=0.85,
            ),
            ValidatedClaim(
                subject="P", predicate="p", object="o3",
                source_urls=["u"], extraction_confidence=0.3, confidence=0.3,
            ),
        ]
        matches = [
            FactMatch(planted_fact_id="f1", match_strategy_used=MatchStrategy.exact, match_score=1.0, matched_claim_id=claims[0].id),
            FactMatch(planted_fact_id="f2", match_strategy_used=MatchStrategy.exact, match_score=1.0, matched_claim_id=claims[1].id),
            FactMatch(planted_fact_id="f3", match_strategy_used=MatchStrategy.exact, match_score=0.0, matched_claim_id=None),
        ]
        buckets, ece = compute_calibration(claims, matches)
        assert len(buckets) == 5
        high_bucket = next(b for b in buckets if b.range_low == 0.8)
        assert high_bucket.claim_count == 2
        assert high_bucket.matched_count == 2
        assert high_bucket.observed_precision == 1.0
        low_bucket = next(b for b in buckets if b.range_low == 0.2)
        assert low_bucket.claim_count == 1
        assert low_bucket.observed_precision == 0.0
        assert 0.0 <= ece <= 1.0

    def test_empty_claims(self) -> None:
        buckets, ece = compute_calibration([], [])
        assert len(buckets) == 5
        assert all(b.claim_count == 0 for b in buckets)
        assert ece == 0.0


class TestComputeRiskRecall:
    def test_all_found(self) -> None:
        matches = [
            RiskMatch(planted_risk_id="risk_t01", matched_flag_index=0, severity_match=True),
            RiskMatch(planted_risk_id="risk_t02", matched_flag_index=1, severity_match=True),
        ]
        from eval.schemas import PlantedRisk
        risks = [
            PlantedRisk(id="risk_t01", risk_category=RiskCategory.REGULATORY, expected_severity=RiskSeverity.MEDIUM, description="d", evidence_source_urls=["u"]),
            PlantedRisk(id="risk_t02", risk_category=RiskCategory.NETWORK, expected_severity=RiskSeverity.HIGH, description="d", evidence_source_urls=["u"]),
        ]
        assert compute_risk_recall(matches, risks) == 1.0

    def test_none_found(self) -> None:
        matches = [
            RiskMatch(planted_risk_id="risk_t01", matched_flag_index=None, severity_match=False),
        ]
        from eval.schemas import PlantedRisk
        risks = [
            PlantedRisk(id="risk_t01", risk_category=RiskCategory.REGULATORY, expected_severity=RiskSeverity.MEDIUM, description="d", evidence_source_urls=["u"]),
        ]
        assert compute_risk_recall(matches, risks) == 0.0

    def test_no_risks(self) -> None:
        assert compute_risk_recall([], []) == 1.0


class TestCostSummary:
    def test_basic(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            artifacts = RunArtifacts(
                persona_id="p1",
                run_id="r1",
                agent_run_dir=d,
                report_json=d / "report.json",
                audit_json=d / "audit.json",
                cost_dollars=1.23,
                duration_seconds=45.6,
                iterations_used=3,
                search_calls_used=12,
                exit_code=0,
            )
            (d / "report.json").write_text("{}")
            (d / "audit.json").write_text("{}")
            summary = cost_summary(artifacts)
            assert summary["cost_dollars"] == 1.23
            assert summary["duration_seconds"] == 45.6


class TestEvaluateSuccessCriteria:
    def test_pass_all(self) -> None:
        metrics = PersonaMetrics(
            persona_id="p1",
            recall_by_tier={Tier.easy: 0.85, Tier.medium: 0.6, Tier.hard: 0.3},
            precision=0.95,
            precision_sample_size=10,
            precision_is_automated=True,
            risk_recall=1.0,
            fact_matches=[],
            risk_matches=[],
            calibration_buckets=[
                CalibrationBucket(range_low=0.0, range_high=0.2, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.2, range_high=0.4, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.4, range_high=0.6, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.6, range_high=0.8, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.8, range_high=1.0, claim_count=2, matched_count=2, observed_precision=1.0),
            ],
            expected_calibration_error=0.05,
            cost_dollars=1.0,
            duration_seconds=30.0,
            success_criteria={},
        )
        criteria = evaluate_success_criteria(metrics)
        assert criteria["high_confidence_precision"] is True
        assert criteria["easy_recall"] is True
        assert criteria["risk_recall"] is True

    def test_fail_easy_recall(self) -> None:
        metrics = PersonaMetrics(
            persona_id="p1",
            recall_by_tier={Tier.easy: 0.7, Tier.medium: 0.6, Tier.hard: 0.3},
            precision=0.95,
            precision_sample_size=10,
            precision_is_automated=True,
            risk_recall=1.0,
            fact_matches=[],
            risk_matches=[],
            calibration_buckets=[
                CalibrationBucket(range_low=0.0, range_high=0.2, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.2, range_high=0.4, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.4, range_high=0.6, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.6, range_high=0.8, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.8, range_high=1.0, claim_count=2, matched_count=2, observed_precision=1.0),
            ],
            expected_calibration_error=0.05,
            cost_dollars=1.0,
            duration_seconds=30.0,
            success_criteria={},
        )
        criteria = evaluate_success_criteria(metrics)
        assert criteria["easy_recall"] is False
        assert criteria["high_confidence_precision"] is True
        assert criteria["risk_recall"] is True

    def test_fail_risk_recall(self) -> None:
        metrics = PersonaMetrics(
            persona_id="p1",
            recall_by_tier={Tier.easy: 0.9, Tier.medium: 0.6, Tier.hard: 0.3},
            precision=0.95,
            precision_sample_size=10,
            precision_is_automated=True,
            risk_recall=0.5,
            fact_matches=[],
            risk_matches=[],
            calibration_buckets=[
                CalibrationBucket(range_low=0.0, range_high=0.2, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.2, range_high=0.4, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.4, range_high=0.6, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.6, range_high=0.8, claim_count=0, matched_count=0, observed_precision=None),
                CalibrationBucket(range_low=0.8, range_high=1.0, claim_count=2, matched_count=2, observed_precision=1.0),
            ],
            expected_calibration_error=0.05,
            cost_dollars=1.0,
            duration_seconds=30.0,
            success_criteria={},
        )
        criteria = evaluate_success_criteria(metrics)
        assert criteria["risk_recall"] is False
