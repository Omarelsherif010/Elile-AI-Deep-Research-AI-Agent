from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from research_agent.errors import GuardrailViolation
from research_agent.schemas import (
    RiskCategory,
    RiskFlag,
    RiskSeverity,
    TargetProfile,
    ValidatedClaim,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run-report")
    state.update(overrides)
    return state


def _make_validated_claim(claim_id: str = "claim-001") -> ValidatedClaim:
    return ValidatedClaim(
        id=claim_id,
        subject="Jane Doe",
        predicate="role",
        object="CEO of Acme Corp",
        source_urls=["https://example.com"],
        extraction_confidence=0.8,
        confidence=0.75,
        validation_notes="ok",
    )


def _make_risk_flag(
    flag_type: RiskCategory = RiskCategory.REGULATORY,
    severity: RiskSeverity = RiskSeverity.HIGH,
) -> RiskFlag:
    return RiskFlag(
        type=flag_type,
        severity=severity,
        description="Regulatory action in 2022.",
        evidence_claim_ids=["claim-001"],
        confidence=0.85,
    )


def _make_report_markdown() -> str:
    return (
        "# Research Report: Jane Doe\n\n"
        "## Scope and Limitations\n"
        "Public sources only.\n\n"
        "## Findings\n"
        "Test findings.\n"
    )


class TestNodeReporter(unittest.TestCase):
    """Unit tests for the reporter node."""

    def setUp(self) -> None:
        self._original_dir = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._original_dir)

    @patch("research_agent.nodes.reporter.Guardrails")
    @patch("research_agent.nodes.reporter._router")
    def test_reporter_writes_report_md_and_json(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """reporter() should write report.md and report.json to the run directory."""
        mock_router.call.return_value = (_make_report_markdown(), 500, 1000)
        mock_guardrails = MagicMock()
        mock_guardrails.check_output_safety.side_effect = lambda text: text
        MockGuardrails.return_value = mock_guardrails

        claim = _make_validated_claim()
        state = _make_state(
            run_id="report-test-001",
            validated_claims=[claim],
            risk_flags=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.reporter import reporter

            result = reporter(state)

            run_dir = os.path.join(tmpdir, "runs", "report-test-001")
            self.assertTrue(os.path.exists(os.path.join(run_dir, "report.md")))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "report.json")))

        self.assertEqual(result, {})

    @patch("research_agent.nodes.reporter.Guardrails")
    @patch("research_agent.nodes.reporter._router")
    def test_risk_flags_sorted_by_severity_in_json(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """reporter() should sort risk_flags by severity desc in report.json."""
        mock_router.call.return_value = (_make_report_markdown(), 500, 1000)
        mock_guardrails = MagicMock()
        mock_guardrails.check_output_safety.side_effect = lambda text: text
        MockGuardrails.return_value = mock_guardrails

        low_flag = _make_risk_flag(RiskCategory.REPUTATIONAL, RiskSeverity.LOW)
        critical_flag = _make_risk_flag(RiskCategory.REGULATORY, RiskSeverity.CRITICAL)
        medium_flag = _make_risk_flag(RiskCategory.FINANCIAL, RiskSeverity.MEDIUM)

        state = _make_state(
            run_id="report-sort-test",
            validated_claims=[_make_validated_claim()],
            risk_flags=[low_flag, critical_flag, medium_flag],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.reporter import reporter

            reporter(state)

            report_json_path = os.path.join(tmpdir, "runs", "report-sort-test", "report.json")
            data = json.loads(open(report_json_path).read())
            severities = [f["severity"] for f in data["risk_flags"]]

        self.assertEqual(severities[0], "CRITICAL")
        self.assertEqual(severities[-1], "LOW")

    @patch("research_agent.nodes.reporter.Guardrails")
    @patch("research_agent.nodes.reporter._router")
    def test_guardrail_violation_falls_back_to_minimal_report(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """reporter() should write a fallback report when guardrail violation is raised."""
        mock_router.call.return_value = ("report with SSN: 123-45-6789", 500, 1000)
        mock_guardrails = MagicMock()
        mock_guardrails.check_output_safety.side_effect = GuardrailViolation(
            "pii_in_output", "PII detected"
        )
        MockGuardrails.return_value = mock_guardrails

        state = _make_state(
            run_id="report-guardrail-test",
            validated_claims=[_make_validated_claim()],
            risk_flags=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.reporter import reporter

            reporter(state)

            report_md_path = os.path.join(tmpdir, "runs", "report-guardrail-test", "report.md")
            content = open(report_md_path).read()

        self.assertIn("Scope and Limitations", content)
        self.assertNotIn("123-45-6789", content)

    @patch("research_agent.nodes.reporter.Guardrails")
    @patch("research_agent.nodes.reporter._router")
    def test_report_json_contains_required_keys(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """report.json must contain all required top-level keys."""
        mock_router.call.return_value = (_make_report_markdown(), 500, 1000)
        mock_guardrails = MagicMock()
        mock_guardrails.check_output_safety.side_effect = lambda text: text
        MockGuardrails.return_value = mock_guardrails

        state = _make_state(
            run_id="report-keys-test",
            validated_claims=[_make_validated_claim()],
            risk_flags=[_make_risk_flag()],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.reporter import reporter

            reporter(state)

            report_json_path = os.path.join(tmpdir, "runs", "report-keys-test", "report.json")
            data = json.loads(open(report_json_path).read())

        required_keys = [
            "run_id",
            "target",
            "claim_count",
            "risk_flag_count",
            "risk_flags",
            "claims",
            "budget_used",
            "entities",
            "relations",
        ]
        for key in required_keys:
            self.assertIn(key, data, f"Missing key: {key}")

    @patch("research_agent.nodes.reporter.Guardrails")
    @patch("research_agent.nodes.reporter._router")
    def test_reporter_returns_empty_dict(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """reporter() should return an empty dict (side-effect node)."""
        mock_router.call.return_value = (_make_report_markdown(), 500, 1000)
        mock_guardrails = MagicMock()
        mock_guardrails.check_output_safety.side_effect = lambda text: text
        MockGuardrails.return_value = mock_guardrails

        state = _make_state(
            run_id="report-empty-return",
            validated_claims=[],
            risk_flags=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.reporter import reporter

            result = reporter(state)

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
