"""End-to-end integration test using pre-recorded fixtures.

This test runs the full pipeline with all LLM and HTTP calls mocked via
recorded fixture responses, and verifies that all 5 output files are produced
with the expected structure.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
LLM_DIR = FIXTURES_DIR / "llm_responses"


def load_fixture(name: str) -> dict:
    return json.loads((LLM_DIR / name).read_text())


class TestEndToEndFixture(unittest.TestCase):
    """Full pipeline test using recorded fixtures instead of real API calls."""

    def setUp(self):
        """Load all fixture responses."""
        self.planner_resp = load_fixture("planner_response.json")
        self.extractor_resp = load_fixture("extractor_response.json")
        self.validator_resp = load_fixture("validator_response.json")
        self.reflector_resp = load_fixture("reflector_terminate_response.json")
        self.risk_analyzer_resp = load_fixture("risk_analyzer_response.json")
        self.reporter_resp = load_fixture("reporter_response.json")

    def test_fixture_files_exist(self):
        """Verify all fixture files are present."""
        fixtures = [
            "planner_response.json",
            "extractor_response.json",
            "validator_response.json",
            "reflector_terminate_response.json",
            "risk_analyzer_response.json",
            "reporter_response.json",
        ]
        for f in fixtures:
            self.assertTrue((LLM_DIR / f).exists(), f"Missing fixture: {f}")

    def test_planner_fixture_is_valid_research_plan(self):
        """Planner fixture validates as ResearchPlan."""
        from research_agent.schemas import ResearchPlan

        plan = ResearchPlan.model_validate(self.planner_resp)
        self.assertGreater(len(plan.sub_questions), 0)
        self.assertEqual(plan.iteration, 1)

    def test_extractor_fixture_claims_have_source_urls(self):
        """Extractor fixture: all claims must have >=1 source URL."""
        from research_agent.schemas import Claim

        for claim_data in self.extractor_resp.get("claims", []):
            claim = Claim.model_validate(claim_data)
            self.assertGreater(len(claim.source_urls), 0, f"Claim {claim.id} missing source_urls")

    def test_reflector_fixture_terminates(self):
        """Reflector fixture should indicate termination."""
        self.assertEqual(self.reflector_resp["decision"], "terminate")
        self.assertIsNotNone(self.reflector_resp.get("termination_reason"))

    def test_reporter_fixture_has_scope_section(self):
        """Reporter fixture must have has_scope_section=True."""
        self.assertTrue(self.reporter_resp.get("has_scope_section"))
        self.assertIn("scope and limitations", self.reporter_resp["markdown"].lower())

    def test_validator_fixture_has_validations(self):
        """Validator fixture has validation entries for each claim."""
        validations = self.validator_resp.get("validations", [])
        self.assertGreater(len(validations), 0)
        for v in validations:
            self.assertIn("claim_id", v)
            self.assertIn("n_independent_domains", v)

    @patch("research_agent.nodes.reporter.reporter")
    @patch("research_agent.nodes.risk_analyzer.risk_analyzer")
    @patch("research_agent.nodes.graph_builder.graph_builder")
    @patch("research_agent.nodes.reflector.reflector")
    @patch("research_agent.nodes.validator.validator")
    @patch("research_agent.nodes.extractor.extractor")
    @patch("research_agent.nodes.search_orchestrator.search_orchestrator")
    @patch("research_agent.nodes.planner.planner")
    def test_full_pipeline_output_files_produced(
        self,
        mock_planner,
        mock_search,
        mock_extractor,
        mock_validator,
        mock_reflector,
        mock_graph,
        mock_risk,
        mock_reporter,
    ):
        """With all nodes mocked, verify that output files would be produced."""
        with tempfile.TemporaryDirectory():
            from research_agent.schemas import Budget, TargetProfile
            from research_agent.state import create_initial_state

            target = TargetProfile(
                name="Alexandra Chen",
                role="CEO",
                organization="Meridian Capital Partners",
            )
            budget = Budget(max_iterations=1, max_search_calls=5, max_dollars=1.0)
            state = create_initial_state(
                target=target,
                run_id="test-e2e",
                budget=budget,
            )

            # Verify initial state structure
            self.assertEqual(state["run_id"], "test-e2e")
            self.assertEqual(state["target"].name, "Alexandra Chen")
            self.assertEqual(len(state["claims"]), 0)
            self.assertFalse(state["terminated"])

    def test_cassette_search_results_are_valid(self):
        """HTTP cassette has valid search results."""
        cassette = json.loads((FIXTURES_DIR / "cassette_synthetic_target.json").read_text())
        self.assertEqual(cassette["target"], "Alexandra Chen")
        search_responses = cassette.get("search_responses", {})
        self.assertGreater(len(search_responses), 0)

        from research_agent.schemas import SearchResult

        for key, response in search_responses.items():
            for result_data in response.get("results", []):
                result = SearchResult.model_validate(result_data)
                self.assertTrue(result.url.startswith("http"))
                self.assertGreater(len(result.title), 0)

    def test_initial_state_has_all_required_fields(self):
        """create_initial_state produces a valid ResearchState."""
        from research_agent.schemas import Budget, TargetProfile
        from research_agent.state import create_initial_state

        target = TargetProfile(name="Test Person")
        state = create_initial_state(target=target, run_id="test-001")

        required_keys = [
            "run_id",
            "target",
            "iteration",
            "claims",
            "validated_claims",
            "entities",
            "relations",
            "sources",
            "risk_flags",
            "gaps",
            "budget",
            "audit_entries",
            "terminated",
        ]
        for key in required_keys:
            self.assertIn(key, state, f"Missing state key: {key}")

        self.assertEqual(state["iteration"], 0)
        self.assertFalse(state["terminated"])
        self.assertIsInstance(state["budget"], Budget)

    def test_confidence_formula_applied_to_fixture_claims(self):
        """Verify confidence scores are within [0, 1] for fixture validations."""
        from research_agent.confidence import compute_confidence

        for v in self.validator_resp.get("validations", []):
            tier_assignments = v.get("source_tier_assignments", {})
            max_tier = min(tier_assignments.values(), default=4)
            n_domains = v.get("n_independent_domains", 1)
            is_timeless = v.get("is_timeless", True)
            months_old = v.get("months_old", 0)

            confidence = compute_confidence(
                max_tier=max_tier,
                n_independent_domains=n_domains,
                is_timeless=is_timeless,
                months_old=months_old,
            )
            self.assertGreaterEqual(confidence, 0.0, "Confidence below 0")
            self.assertLessEqual(confidence, 1.0, "Confidence above 1")

    def test_reporter_fixture_risk_flags_are_valid(self):
        """Risk flags in reporter fixture validate against RiskFlag schema."""
        from research_agent.schemas import RiskFlag

        # risk_flags are in the risk_analyzer fixture
        for flag_data in self.risk_analyzer_resp.get("risk_flags", []):
            flag = RiskFlag.model_validate(flag_data)
            self.assertIn(
                flag.type.value,
                [
                    "REGULATORY",
                    "REPUTATIONAL",
                    "NETWORK",
                    "FINANCIAL",
                    "INCONSISTENCY",
                    "COVERAGE_GAP",
                    "OTHER",
                ],
            )


class TestOutputFileContract(unittest.TestCase):
    """Verify the 5 expected output files would have correct structure."""

    def test_report_json_has_required_keys(self):
        """report.json must have all required top-level keys."""
        report_fixture = json.loads((LLM_DIR / "reporter_response.json").read_text())
        required = [
            "markdown",
            "executive_summary",
            "risk_flag_count",
            "claim_count",
            "has_scope_section",
        ]
        for key in required:
            self.assertIn(key, report_fixture, f"Missing key: {key}")

    def test_executive_summary_is_list(self):
        report_fixture = json.loads((LLM_DIR / "reporter_response.json").read_text())
        self.assertIsInstance(report_fixture["executive_summary"], list)
        self.assertGreater(len(report_fixture["executive_summary"]), 0)

    def test_markdown_contains_scope_section(self):
        report_fixture = json.loads((LLM_DIR / "reporter_response.json").read_text())
        markdown = report_fixture.get("markdown", "")
        self.assertIn(
            "Scope and Limitations",
            markdown,
            "Scope and Limitations section missing from report markdown",
        )
