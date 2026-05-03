from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from research_agent.schemas import (
    RiskCategory,
    RiskFlag,
    TargetProfile,
    ValidatedClaim,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run-risk")
    state.update(overrides)
    return state


def _make_validated_claim(
    claim_id: str = "claim-001",
    url: str = "https://example.com",
) -> ValidatedClaim:
    return ValidatedClaim(
        id=claim_id,
        subject="Jane Doe",
        predicate="role",
        object="CEO of Acme Corp",
        source_urls=[url],
        extraction_confidence=0.8,
        confidence=0.75,
        validation_notes="ok",
    )


def _make_risk_flag_json(
    flag_type: str = "REGULATORY",
    severity: str = "HIGH",
    with_justification: bool = True,
) -> dict:
    flag = {
        "type": flag_type,
        "severity": severity,
        "description": "SEC enforcement action in 2022.",
        "evidence_claim_ids": ["claim-001"],
        "confidence": 0.85,
    }
    if flag_type == "OTHER":
        flag["justification"] = "Custom risk" if with_justification else None
    return flag


class TestNodeRiskAnalyzer(unittest.TestCase):
    """Unit tests for the risk_analyzer node."""

    @patch("research_agent.nodes.risk_analyzer._router")
    def test_risk_analyzer_returns_risk_flags(self, mock_router: MagicMock) -> None:
        """risk_analyzer() should return a non-empty risk_flags list from LLM output."""
        flag_data = _make_risk_flag_json("REGULATORY", "HIGH")
        mock_router.call.return_value = (
            json.dumps({"risk_flags": [flag_data]}),
            100,
            200,
        )
        claim = _make_validated_claim()
        state = _make_state(validated_claims=[claim])

        from research_agent.nodes.risk_analyzer import risk_analyzer

        result = risk_analyzer(state)

        self.assertIn("risk_flags", result)
        self.assertGreater(len(result["risk_flags"]), 0)
        self.assertIsInstance(result["risk_flags"][0], RiskFlag)

    @patch("research_agent.nodes.risk_analyzer._router")
    def test_other_flag_without_justification_gets_default(self, mock_router: MagicMock) -> None:
        """risk_analyzer() should set a default justification for OTHER flags missing one."""
        flag_data = {
            "type": "OTHER",
            "severity": "LOW",
            "description": "Unusual pattern",
            "evidence_claim_ids": [],
            "confidence": 0.4,
            "justification": None,
        }
        mock_router.call.return_value = (
            json.dumps({"risk_flags": [flag_data]}),
            100,
            200,
        )
        claim = _make_validated_claim()
        state = _make_state(validated_claims=[claim])

        from research_agent.nodes.risk_analyzer import risk_analyzer

        result = risk_analyzer(state)

        flags = result["risk_flags"]
        self.assertEqual(len(flags), 1)
        self.assertIsNotNone(flags[0].justification)
        self.assertIn("flagged for review", flags[0].justification)

    @patch("research_agent.nodes.risk_analyzer._router")
    def test_llm_failure_returns_empty_risk_flags(self, mock_router: MagicMock) -> None:
        """risk_analyzer() should return empty risk_flags list on LLM failure (no crash)."""
        mock_router.call.side_effect = Exception("LLM unavailable")
        claim = _make_validated_claim()
        state = _make_state(validated_claims=[claim])

        from research_agent.nodes.risk_analyzer import risk_analyzer

        result = risk_analyzer(state)

        self.assertIn("risk_flags", result)
        self.assertEqual(len(result["risk_flags"]), 0)

    @patch("research_agent.nodes.risk_analyzer._router")
    def test_invalid_flag_data_is_skipped(self, mock_router: MagicMock) -> None:
        """risk_analyzer() should skip invalid flag dicts without crashing."""
        mock_router.call.return_value = (
            json.dumps(
                {
                    "risk_flags": [
                        {"type": "INVALID_TYPE", "severity": "ULTRA", "description": "bad"},
                        _make_risk_flag_json("REPUTATIONAL", "MEDIUM"),
                    ]
                }
            ),
            100,
            200,
        )
        state = _make_state(validated_claims=[_make_validated_claim()])

        from research_agent.nodes.risk_analyzer import risk_analyzer

        result = risk_analyzer(state)

        self.assertIn("risk_flags", result)
        valid_flags = [f for f in result["risk_flags"] if f.type == RiskCategory.REPUTATIONAL]
        self.assertEqual(len(valid_flags), 1)

    @patch("research_agent.nodes.risk_analyzer._router")
    def test_empty_validated_claims_returns_empty_flags(self, mock_router: MagicMock) -> None:
        """risk_analyzer() should work with empty validated_claims."""
        mock_router.call.return_value = (
            json.dumps({"risk_flags": []}),
            50,
            50,
        )
        state = _make_state(validated_claims=[])

        from research_agent.nodes.risk_analyzer import risk_analyzer

        result = risk_analyzer(state)

        self.assertEqual(result["risk_flags"], [])


if __name__ == "__main__":
    unittest.main()
