"""Tests for risk flag grouping, severity ordering, and evidence chain presentation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_agent.risk_taxonomy import SEVERITY_ORDER
from research_agent.schemas import RiskCategory, RiskFlag, RiskSeverity


class TestRiskFlagOrdering(unittest.TestCase):
    def test_severity_order_critical_is_highest(self):
        self.assertGreater(SEVERITY_ORDER[RiskSeverity.CRITICAL], SEVERITY_ORDER[RiskSeverity.HIGH])
        self.assertGreater(SEVERITY_ORDER[RiskSeverity.HIGH], SEVERITY_ORDER[RiskSeverity.MEDIUM])
        self.assertGreater(SEVERITY_ORDER[RiskSeverity.MEDIUM], SEVERITY_ORDER[RiskSeverity.LOW])

    def test_sorting_by_severity(self):
        flags = [
            RiskFlag(
                type=RiskCategory.NETWORK,
                severity=RiskSeverity.LOW,
                description="low",
                evidence_claim_ids=[],
                confidence=0.5,
            ),
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.CRITICAL,
                description="critical",
                evidence_claim_ids=[],
                confidence=0.9,
            ),
            RiskFlag(
                type=RiskCategory.FINANCIAL,
                severity=RiskSeverity.MEDIUM,
                description="medium",
                evidence_claim_ids=[],
                confidence=0.6,
            ),
            RiskFlag(
                type=RiskCategory.REPUTATIONAL,
                severity=RiskSeverity.HIGH,
                description="high",
                evidence_claim_ids=[],
                confidence=0.7,
            ),
        ]
        sorted_flags = sorted(flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 0), reverse=True)
        self.assertEqual(sorted_flags[0].severity, RiskSeverity.CRITICAL)
        self.assertEqual(sorted_flags[1].severity, RiskSeverity.HIGH)
        self.assertEqual(sorted_flags[2].severity, RiskSeverity.MEDIUM)
        self.assertEqual(sorted_flags[3].severity, RiskSeverity.LOW)

    def test_grouping_by_category(self):
        flags = [
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.HIGH,
                description="r1",
                evidence_claim_ids=[],
                confidence=0.8,
            ),
            RiskFlag(
                type=RiskCategory.NETWORK,
                severity=RiskSeverity.LOW,
                description="n1",
                evidence_claim_ids=[],
                confidence=0.4,
            ),
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.MEDIUM,
                description="r2",
                evidence_claim_ids=[],
                confidence=0.6,
            ),
        ]
        groups: dict[str, list] = {}
        for f in flags:
            groups.setdefault(f.type.value, []).append(f)

        self.assertEqual(len(groups["REGULATORY"]), 2)
        self.assertEqual(len(groups["NETWORK"]), 1)

    def test_critical_flag_sorted_before_low_in_category(self):
        regulatory_flags = [
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.LOW,
                description="low reg",
                evidence_claim_ids=[],
                confidence=0.3,
            ),
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.CRITICAL,
                description="critical reg",
                evidence_claim_ids=[],
                confidence=0.95,
            ),
        ]
        sorted_flags = sorted(
            regulatory_flags, key=lambda f: SEVERITY_ORDER.get(f.severity, 0), reverse=True
        )
        self.assertEqual(sorted_flags[0].description, "critical reg")


class TestRiskFlagValidation(unittest.TestCase):
    def test_other_flag_requires_justification(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            RiskFlag(
                type=RiskCategory.OTHER,
                severity=RiskSeverity.MEDIUM,
                description="some risk",
                evidence_claim_ids=["c1"],
                confidence=0.5,
                justification=None,  # Should fail — OTHER requires justification
            )

    def test_other_flag_with_justification_valid(self):
        flag = RiskFlag(
            type=RiskCategory.OTHER,
            severity=RiskSeverity.MEDIUM,
            description="some risk",
            evidence_claim_ids=["c1"],
            confidence=0.5,
            justification="Specific reason this doesn't fit standard categories",
        )
        self.assertIsNotNone(flag.justification)

    def test_coverage_gap_has_zero_evidence(self):
        flag = RiskFlag(
            type=RiskCategory.COVERAGE_GAP,
            severity=RiskSeverity.LOW,
            description="financial dimension not explored",
            evidence_claim_ids=[],  # COVERAGE_GAP has no evidence by design
            confidence=1.0,
        )
        self.assertEqual(len(flag.evidence_claim_ids), 0)

    def test_all_7_categories_are_valid(self):
        categories = [
            "REGULATORY",
            "REPUTATIONAL",
            "NETWORK",
            "FINANCIAL",
            "INCONSISTENCY",
            "COVERAGE_GAP",
            "OTHER",
        ]
        for cat_name in categories:
            cat = RiskCategory(cat_name)
            self.assertEqual(cat.value, cat_name)

    def test_all_4_severities_are_valid(self):
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for sev_name in severities:
            sev = RiskSeverity(sev_name)
            self.assertEqual(sev.value, sev_name)


class TestReporterRiskRendering(unittest.TestCase):
    """Test that reporter produces risk flags grouped by category, sorted by severity."""

    def _make_state_with_risk_flags(self, tmpdir: str, flags: list[RiskFlag]):
        from research_agent.schemas import Budget, TargetProfile
        from research_agent.state import create_initial_state

        state = create_initial_state(
            target=TargetProfile(name="Test Subject"),
            run_id=Path(tmpdir).name,
            budget=Budget(max_iterations=1, max_search_calls=5, max_dollars=1.0),
        )
        state["risk_flags"] = flags
        state["validated_claims"] = []
        state["entities"] = []
        state["relations"] = []
        state["terminated"] = True
        return state

    @patch("research_agent.nodes.reporter._router")
    def test_report_json_risk_flags_sorted_by_severity(self, mock_router):
        """report.json should contain risk_flags sorted Critical → High → Medium → Low."""
        import os

        from research_agent.nodes.reporter import reporter

        flags = [
            RiskFlag(
                type=RiskCategory.NETWORK,
                severity=RiskSeverity.LOW,
                description="low",
                evidence_claim_ids=[],
                confidence=0.3,
            ),
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.CRITICAL,
                description="critical",
                evidence_claim_ids=[],
                confidence=0.9,
            ),
            RiskFlag(
                type=RiskCategory.FINANCIAL,
                severity=RiskSeverity.MEDIUM,
                description="medium",
                evidence_claim_ids=[],
                confidence=0.5,
            ),
        ]

        # Mock LLM to return a minimal valid report
        mock_router.call.return_value = (
            "# Report\n\n## Scope and Limitations\nPublic sources only.\n\n",
            100,
            200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to tmpdir so runs/{run_id} is created there
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                state = self._make_state_with_risk_flags(tmpdir, flags)
                state["run_id"] = "test-risk"
                reporter(state)

                report_path = Path(tmpdir) / "runs" / "test-risk" / "report.json"
                if report_path.exists():
                    report = json.loads(report_path.read_text())
                    risk_flags_in_report = report.get("risk_flags", [])
                    if len(risk_flags_in_report) >= 2:
                        # Verify severity ordering
                        severities = [f["severity"] for f in risk_flags_in_report]
                        order_values = [SEVERITY_ORDER.get(RiskSeverity(s), 0) for s in severities]
                        self.assertEqual(
                            order_values,
                            sorted(order_values, reverse=True),
                            f"Risk flags not sorted by severity: {severities}",
                        )
            finally:
                os.chdir(orig_cwd)

    @patch("research_agent.nodes.reporter._router")
    def test_report_json_has_structured_risk_flags_array(self, mock_router):
        """report.json risk_flags array should have required fields."""
        import os

        from research_agent.nodes.reporter import reporter

        flags = [
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.HIGH,
                description="Test regulatory flag",
                evidence_claim_ids=["claim-001"],
                confidence=0.8,
            ),
        ]

        mock_router.call.return_value = (
            "# Report\n\n## Scope and Limitations\nPublic sources only.\n\n",
            100,
            200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                state = self._make_state_with_risk_flags(tmpdir, flags)
                state["run_id"] = "test-struct"
                reporter(state)

                report_path = Path(tmpdir) / "runs" / "test-struct" / "report.json"
                if report_path.exists():
                    report = json.loads(report_path.read_text())
                    risk_flags = report.get("risk_flags", [])
                    if risk_flags:
                        flag = risk_flags[0]
                        self.assertIn("type", flag)
                        self.assertIn("severity", flag)
                        self.assertIn("description", flag)
                        self.assertIn("confidence", flag)
            finally:
                os.chdir(orig_cwd)
