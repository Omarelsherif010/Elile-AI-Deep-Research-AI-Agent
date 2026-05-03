"""Unit tests for eval/schemas.py."""

from __future__ import annotations

import pytest
from eval.schemas import (
    CalibrationBucket,
    FactType,
    MatchStrategy,
    PersonaDefinition,
    PersonaType,
    PlantedFact,
    PlantedRisk,
    ResearchDimension,
    Tier,
)
from pydantic import ValidationError

from research_agent.schemas import RiskCategory, RiskSeverity


class TestEnums:
    def test_tier_values(self) -> None:
        assert Tier.easy == "easy"
        assert Tier.medium == "medium"
        assert Tier.hard == "hard"

    def test_research_dimension_values(self) -> None:
        assert ResearchDimension.biographical == "biographical"
        assert ResearchDimension.professional_history == "professional_history"

    def test_match_strategy_values(self) -> None:
        assert MatchStrategy.exact == "exact"
        assert MatchStrategy.fuzzy == "fuzzy"
        assert MatchStrategy.semantic == "semantic"


class TestPlantedFact:
    def test_valid_fact(self) -> None:
        fact = PlantedFact(
            id="fact_a01",
            statement="Founded Vellinor Capital in 2019",
            difficulty=Tier.easy,
            expected_dimension=ResearchDimension.professional_history,
            fact_type=FactType.role,
            match_strategy=MatchStrategy.fuzzy,
            match_threshold=80.0,
            notes="Headline-visible fact",
            source_urls=["https://example.com/source"],
        )
        assert fact.id == "fact_a01"
        assert fact.match_threshold == 80.0

    def test_invalid_id_pattern(self) -> None:
        with pytest.raises(ValidationError):
            PlantedFact(
                id="invalid",
                statement="test",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical,
                notes="test",
                source_urls=["https://example.com"],
            )

    def test_empty_statement(self) -> None:
        with pytest.raises(ValidationError):
            PlantedFact(
                id="fact_a01",
                statement="",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical,
                notes="test",
                source_urls=["https://example.com"],
            )

    def test_empty_source_urls(self) -> None:
        with pytest.raises(ValidationError):
            PlantedFact(
                id="fact_a01",
                statement="test",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical,
                notes="test",
                source_urls=[],
            )

    def test_fuzzy_threshold_range(self) -> None:
        with pytest.raises(ValidationError):
            PlantedFact(
                id="fact_a01",
                statement="test",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical,
                match_strategy=MatchStrategy.fuzzy,
                match_threshold=150.0,
                notes="test",
                source_urls=["https://example.com"],
            )

    def test_semantic_threshold_range(self) -> None:
        with pytest.raises(ValidationError):
            PlantedFact(
                id="fact_a01",
                statement="test",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type=FactType.biographical,
                match_strategy=MatchStrategy.semantic,
                match_threshold=1.5,
                notes="test",
                source_urls=["https://example.com"],
            )


class TestPlantedRisk:
    def test_valid_risk(self) -> None:
        risk = PlantedRisk(
            id="risk_a01",
            risk_category=RiskCategory.REGULATORY,
            expected_severity=RiskSeverity.HIGH,
            description="Test risk",
            evidence_source_urls=["https://example.com"],
        )
        assert risk.risk_category == RiskCategory.REGULATORY

    def test_invalid_id_pattern(self) -> None:
        with pytest.raises(ValidationError):
            PlantedRisk(
                id="bad_id",
                risk_category=RiskCategory.REGULATORY,
                expected_severity=RiskSeverity.LOW,
                description="test",
                evidence_source_urls=["https://example.com"],
            )


class TestPersonaDefinition:
    def test_valid_synthetic(self) -> None:
        persona = PersonaDefinition(
            id="persona_synthetic_a",
            target_name="Aria Vellinor",
            target_context="Fictional venture capitalist",
            persona_type=PersonaType.synthetic,
            description="Test persona",
            ethical_notes="All fictional",
            planted_facts=[
                PlantedFact(
                    id="fact_a01",
                    statement="Founded Vellinor Capital",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.professional_history,
                    fact_type=FactType.role,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
            plant_site_root="eval/plant_site/aria-vellinor",
        )
        assert persona.id == "persona_synthetic_a"

    def test_synthetic_requires_plant_site_root(self) -> None:
        with pytest.raises(ValidationError):
            PersonaDefinition(
                id="persona_synthetic_a",
                target_name="Aria Vellinor",
                target_context="Fictional",
                persona_type=PersonaType.synthetic,
                description="Test",
                ethical_notes="All fictional",
                planted_facts=[
                    PlantedFact(
                        id="fact_a01",
                        statement="Test fact",
                        difficulty=Tier.easy,
                        expected_dimension=ResearchDimension.biographical,
                        fact_type=FactType.biographical,
                        notes="test",
                        source_urls=["https://example.com"],
                    ),
                ],
            )

    def test_valid_real_public(self) -> None:
        persona = PersonaDefinition(
            id="persona_real_public",
            target_name="Satya Nadella",
            target_context="CEO of Microsoft",
            persona_type=PersonaType.real_public,
            description="Real public figure",
            ethical_notes="Public sources only",
            planted_facts=[
                PlantedFact(
                    id="fact_r01",
                    statement="CEO of Microsoft",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.professional_history,
                    fact_type=FactType.role,
                    notes="test",
                    source_urls=["https://microsoft.com"],
                ),
            ],
        )
        assert persona.plant_site_root is None


class TestCalibrationBucket:
    def test_valid_bucket(self) -> None:
        bucket = CalibrationBucket(
            range_low=0.0,
            range_high=0.2,
            claim_count=5,
            matched_count=3,
            observed_precision=0.6,
        )
        assert bucket.observed_precision == 0.6

    def test_matched_count_exceeds_claim_count(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationBucket(
                range_low=0.0,
                range_high=0.2,
                claim_count=2,
                matched_count=5,
                observed_precision=0.5,
            )

    def test_missing_precision_when_claims_exist(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationBucket(
                range_low=0.0,
                range_high=0.2,
                claim_count=2,
                matched_count=1,
            )


class TestRoundTrip:
    def test_planted_fact_dict_roundtrip(self) -> None:
        original = PlantedFact(
            id="fact_a01",
            statement="Founded Vellinor Capital in 2019",
            difficulty=Tier.easy,
            expected_dimension=ResearchDimension.professional_history,
            fact_type=FactType.role,
            match_strategy=MatchStrategy.fuzzy,
            match_threshold=80.0,
            notes="Headline-visible fact",
            source_urls=["https://example.com/source"],
        )
        data = original.model_dump()
        restored = PlantedFact(**data)
        assert restored.statement == original.statement
        assert restored.difficulty == original.difficulty

    def test_persona_definition_dict_roundtrip(self) -> None:
        persona = PersonaDefinition(
            id="persona_synthetic_a",
            target_name="Aria Vellinor",
            target_context="Fictional venture capitalist",
            persona_type=PersonaType.synthetic,
            description="Test persona",
            ethical_notes="All fictional",
            planted_facts=[
                PlantedFact(
                    id="fact_a01",
                    statement="Founded Vellinor Capital",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.professional_history,
                    fact_type=FactType.role,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
            plant_site_root="eval/plant_site/aria-vellinor",
            planted_risks=[
                PlantedRisk(
                    id="risk_a01",
                    risk_category=RiskCategory.REGULATORY,
                    expected_severity=RiskSeverity.MEDIUM,
                    description="Test risk",
                    evidence_source_urls=["https://example.com"],
                ),
            ],
        )
        data = persona.model_dump()
        restored = PersonaDefinition(**data)
        assert restored.target_name == persona.target_name
        assert len(restored.planted_facts) == 1
        assert len(restored.planted_risks) == 1
