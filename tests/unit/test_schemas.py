from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_agent.schemas import (
    Budget,
    Claim,
    EntityType,
    RiskCategory,
    RiskFlag,
    RiskSeverity,
    TargetProfile,
    ValidatedClaim,
)

# ---------------------------------------------------------------------------
# TargetProfile
# ---------------------------------------------------------------------------


class TestTargetProfile:
    def test_valid_name(self) -> None:
        profile = TargetProfile(name="Jane Doe")
        assert profile.name == "Jane Doe"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="name must not be empty"):
            TargetProfile(name="")

    def test_whitespace_only_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="name must not be empty"):
            TargetProfile(name="   ")

    def test_name_at_200_chars_is_valid(self) -> None:
        name = "a" * 200
        profile = TargetProfile(name=name)
        assert len(profile.name) == 200

    def test_name_over_200_chars_raises(self) -> None:
        name = "a" * 201
        with pytest.raises(ValidationError, match="name must not exceed 200 characters"):
            TargetProfile(name=name)

    def test_defaults(self) -> None:
        profile = TargetProfile(name="Test Person")
        assert profile.aliases == []
        assert profile.role is None
        assert profile.organization is None
        assert profile.context is None
        assert profile.geographic_hint is None


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------


def _make_claim(**kwargs) -> Claim:
    defaults = {
        "subject": "Jane Doe",
        "predicate": "worked_at",
        "object": "Acme Corp",
        "source_urls": ["https://example.com"],
        "extraction_confidence": 0.8,
    }
    defaults.update(kwargs)
    return Claim(**defaults)


class TestClaim:
    def test_valid_claim(self) -> None:
        claim = _make_claim()
        assert claim.subject == "Jane Doe"

    def test_source_urls_required(self) -> None:
        with pytest.raises(ValidationError, match="source_urls must have at least 1 item"):
            _make_claim(source_urls=[])

    def test_multiple_source_urls_valid(self) -> None:
        claim = _make_claim(source_urls=["https://a.com", "https://b.com"])
        assert len(claim.source_urls) == 2

    def test_id_auto_generated(self) -> None:
        claim = _make_claim()
        assert claim.id  # non-empty UUID


# ---------------------------------------------------------------------------
# RiskFlag
# ---------------------------------------------------------------------------


class TestRiskFlag:
    def test_other_without_justification_raises(self) -> None:
        with pytest.raises(ValidationError, match="justification is required when type is OTHER"):
            RiskFlag(
                type=RiskCategory.OTHER,
                severity=RiskSeverity.MEDIUM,
                description="Some risk",
                confidence=0.6,
                justification=None,
            )

    def test_other_with_empty_justification_raises(self) -> None:
        with pytest.raises(ValidationError, match="justification is required when type is OTHER"):
            RiskFlag(
                type=RiskCategory.OTHER,
                severity=RiskSeverity.MEDIUM,
                description="Some risk",
                confidence=0.6,
                justification="",
            )

    def test_other_with_justification_valid(self) -> None:
        flag = RiskFlag(
            type=RiskCategory.OTHER,
            severity=RiskSeverity.HIGH,
            description="Unusual pattern",
            confidence=0.7,
            justification="Manually identified edge case",
        )
        assert flag.type == RiskCategory.OTHER

    def test_non_other_without_justification_valid(self) -> None:
        flag = RiskFlag(
            type=RiskCategory.REGULATORY,
            severity=RiskSeverity.HIGH,
            description="Regulatory issue",
            confidence=0.8,
        )
        assert flag.justification is None


# ---------------------------------------------------------------------------
# ValidatedClaim
# ---------------------------------------------------------------------------


class TestValidatedClaim:
    def test_inherits_from_claim(self) -> None:
        assert issubclass(ValidatedClaim, Claim)

    def test_valid_validated_claim(self) -> None:
        vc = ValidatedClaim(
            subject="Jane Doe",
            predicate="worked_at",
            object="Acme Corp",
            source_urls=["https://example.com"],
            extraction_confidence=0.8,
            confidence=0.9,
        )
        assert vc.confidence == 0.9
        assert vc.supporting_sources == []
        assert vc.contradicts == []
        assert vc.validation_notes == ""

    def test_inherits_source_urls_validation(self) -> None:
        with pytest.raises(ValidationError, match="source_urls must have at least 1 item"):
            ValidatedClaim(
                subject="Jane Doe",
                predicate="worked_at",
                object="Acme Corp",
                source_urls=[],
                extraction_confidence=0.8,
                confidence=0.9,
            )


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class TestBudget:
    def test_default_values(self) -> None:
        budget = Budget()
        assert budget.max_iterations == 8
        assert budget.used_iterations == 0
        assert budget.max_search_calls == 60
        assert budget.used_search_calls == 0
        assert budget.max_dollars == 5.0
        assert budget.used_dollars == 0.0
        assert budget.max_seconds_per_iteration == 180
        assert budget.used_seconds_current_iteration == 0.0
        assert budget.last_iteration_cost == 0.0

    def test_negative_used_iterations_raises(self) -> None:
        with pytest.raises(ValidationError, match="used fields must be >= 0"):
            Budget(used_iterations=-1)

    def test_negative_used_dollars_raises(self) -> None:
        with pytest.raises(ValidationError, match="used fields must be >= 0"):
            Budget(used_dollars=-0.01)

    def test_negative_used_search_calls_raises(self) -> None:
        with pytest.raises(ValidationError, match="used fields must be >= 0"):
            Budget(used_search_calls=-5)

    def test_zero_used_values_valid(self) -> None:
        budget = Budget(used_iterations=0, used_dollars=0.0, used_search_calls=0)
        assert budget.used_iterations == 0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_risk_category_values(self) -> None:
        expected = {
            "REGULATORY",
            "REPUTATIONAL",
            "NETWORK",
            "FINANCIAL",
            "INCONSISTENCY",
            "COVERAGE_GAP",
            "OTHER",
        }
        actual = {member.value for member in RiskCategory}
        assert actual == expected

    def test_risk_severity_values(self) -> None:
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        actual = {member.value for member in RiskSeverity}
        assert actual == expected

    def test_entity_type_values(self) -> None:
        expected = {"PERSON", "ORGANIZATION", "EVENT"}
        actual = {member.value for member in EntityType}
        assert actual == expected

    def test_risk_category_count(self) -> None:
        assert len(RiskCategory) == 7

    def test_risk_severity_count(self) -> None:
        assert len(RiskSeverity) == 4
