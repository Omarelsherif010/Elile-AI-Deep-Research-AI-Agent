from __future__ import annotations

from research_agent.risk_taxonomy import (
    COVERAGE_GAP_DIMENSIONS,
    SEVERITY_ORDER,
    RiskCategory,
    RiskSeverity,
)


class TestRiskCategoryValues:
    def test_all_7_categories_exist(self) -> None:
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

    def test_count_is_7(self) -> None:
        assert len(RiskCategory) == 7

    def test_regulatory_value(self) -> None:
        assert RiskCategory.REGULATORY.value == "REGULATORY"

    def test_coverage_gap_value(self) -> None:
        assert RiskCategory.COVERAGE_GAP.value == "COVERAGE_GAP"


class TestRiskSeverityValues:
    def test_all_4_severities_exist(self) -> None:
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        actual = {member.value for member in RiskSeverity}
        assert actual == expected

    def test_count_is_4(self) -> None:
        assert len(RiskSeverity) == 4


class TestSeverityOrder:
    def test_critical_greater_than_high(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.CRITICAL] > SEVERITY_ORDER[RiskSeverity.HIGH]

    def test_high_greater_than_medium(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.HIGH] > SEVERITY_ORDER[RiskSeverity.MEDIUM]

    def test_medium_greater_than_low(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.MEDIUM] > SEVERITY_ORDER[RiskSeverity.LOW]

    def test_critical_is_4(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.CRITICAL] == 4

    def test_high_is_3(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.HIGH] == 3

    def test_medium_is_2(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.MEDIUM] == 2

    def test_low_is_1(self) -> None:
        assert SEVERITY_ORDER[RiskSeverity.LOW] == 1

    def test_all_severities_covered(self) -> None:
        assert set(SEVERITY_ORDER.keys()) == set(RiskSeverity)

    def test_ordering_is_strict(self) -> None:
        """Verify that sorting by SEVERITY_ORDER gives LOW < MEDIUM < HIGH < CRITICAL."""
        sorted_severities = sorted(RiskSeverity, key=lambda s: SEVERITY_ORDER[s])
        assert sorted_severities == [
            RiskSeverity.LOW,
            RiskSeverity.MEDIUM,
            RiskSeverity.HIGH,
            RiskSeverity.CRITICAL,
        ]


class TestCoverageGapDimensions:
    def test_six_dimensions_exist(self) -> None:
        assert len(COVERAGE_GAP_DIMENSIONS) == 6

    def test_all_expected_dimensions_present(self) -> None:
        expected = {"biographical", "professional", "financial", "network", "statements", "risk"}
        assert COVERAGE_GAP_DIMENSIONS == expected
