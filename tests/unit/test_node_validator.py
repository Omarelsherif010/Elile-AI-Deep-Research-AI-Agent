from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from research_agent.schemas import (
    Claim,
    Source,
    TargetProfile,
    ValidatedClaim,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run")
    state.update(overrides)
    return state


def _make_claim(claim_id: str = "claim-001", url: str = "https://example.com") -> Claim:
    return Claim(
        id=claim_id,
        subject="Jane Doe",
        predicate="role",
        object="CEO of Acme Corp",
        source_urls=[url],
        extraction_confidence=0.7,
    )


def _make_source(url: str = "https://example.com", tier: int = 3) -> Source:
    return Source(
        url=url,
        domain="example.com",
        tier=tier,
        retrieved_at=datetime.now(UTC),
        robots_allowed=True,
    )


def _make_validation_response(
    claim_id: str,
    n_domains: int = 2,
    max_tier: int = 2,
    is_timeless: bool = True,
    months_old: int = 0,
) -> str:
    return json.dumps(
        {
            "validations": [
                {
                    "claim_id": claim_id,
                    "n_independent_domains": n_domains,
                    "source_tier_assignments": {"https://example.com": max_tier},
                    "is_timeless": is_timeless,
                    "months_old": months_old,
                    "contradictions_max_tier": None,
                    "validation_notes": "validated",
                }
            ]
        }
    )


class TestNodeValidator(unittest.TestCase):
    """Unit tests for the validator node."""

    @patch("research_agent.nodes.validator._router")
    def test_validator_produces_validated_claim_for_each_input(
        self, mock_router: MagicMock
    ) -> None:
        """validator() should produce one ValidatedClaim for each input Claim."""
        claim = _make_claim("claim-001")
        mock_router.call.return_value = (
            _make_validation_response("claim-001", n_domains=2, max_tier=2),
            100,
            200,
        )
        source = _make_source(tier=2)
        state = _make_state(claims=[claim], sources=[source], validated_claims=[])

        from research_agent.nodes.validator import validator

        result = validator(state)

        self.assertIn("validated_claims", result)
        self.assertEqual(len(result["validated_claims"]), 1)
        self.assertIsInstance(result["validated_claims"][0], ValidatedClaim)

    @patch("research_agent.nodes.validator._router")
    def test_confidence_cap_applied_when_insufficient_corroboration(
        self, mock_router: MagicMock
    ) -> None:
        """validator() should cap confidence at 0.49 when n_domains < 2 and max_tier > 1."""
        claim = _make_claim("claim-cap")
        mock_router.call.return_value = (
            json.dumps(
                {
                    "validations": [
                        {
                            "claim_id": "claim-cap",
                            "n_independent_domains": 1,
                            "source_tier_assignments": {"https://example.com": 2},
                            "is_timeless": True,
                            "months_old": 0,
                            "contradictions_max_tier": None,
                            "validation_notes": "",
                        }
                    ]
                }
            ),
            50,
            100,
        )
        source = _make_source(tier=2)
        state = _make_state(claims=[claim], sources=[source], validated_claims=[])

        from research_agent.nodes.validator import validator

        result = validator(state)

        vc = result["validated_claims"][0]
        self.assertLessEqual(vc.confidence, 0.49)
        self.assertIn("capped", vc.validation_notes)

    @patch("research_agent.nodes.validator._router")
    def test_llm_failure_uses_default_scoring(self, mock_router: MagicMock) -> None:
        """validator() should fall back to default scoring without raising when LLM fails."""
        mock_router.call.side_effect = Exception("LLM unavailable")
        claim = _make_claim("claim-fallback")
        state = _make_state(claims=[claim], sources=[], validated_claims=[])

        from research_agent.nodes.validator import validator

        result = validator(state)

        self.assertIn("validated_claims", result)
        self.assertEqual(len(result["validated_claims"]), 1)
        vc = result["validated_claims"][0]
        self.assertIsInstance(vc.confidence, float)
        self.assertIn("Defaulted", vc.validation_notes)

    @patch("research_agent.nodes.validator._router")
    def test_already_validated_claims_not_revalidated(self, mock_router: MagicMock) -> None:
        """validator() should skip claims already present in validated_claims."""
        claim = _make_claim("claim-already")
        existing_vc = ValidatedClaim(
            **claim.model_dump(),
            confidence=0.8,
            validation_notes="already validated",
        )
        state = _make_state(claims=[claim], validated_claims=[existing_vc])

        from research_agent.nodes.validator import validator

        result = validator(state)

        self.assertEqual(result, {})
        mock_router.call.assert_not_called()

    @patch("research_agent.nodes.validator._router")
    def test_single_low_tier_source_adds_unverified_note(self, mock_router: MagicMock) -> None:
        """validator() should add an unverified note for single low-tier source claims."""
        claim = _make_claim("claim-lowt")
        mock_router.call.return_value = (
            json.dumps(
                {
                    "validations": [
                        {
                            "claim_id": "claim-lowt",
                            "n_independent_domains": 1,
                            "source_tier_assignments": {"https://example.com": 4},
                            "is_timeless": True,
                            "months_old": 0,
                            "contradictions_max_tier": None,
                            "validation_notes": "",
                        }
                    ]
                }
            ),
            50,
            100,
        )
        source = _make_source(tier=4)
        state = _make_state(claims=[claim], sources=[source], validated_claims=[])

        from research_agent.nodes.validator import validator

        result = validator(state)

        vc = result["validated_claims"][0]
        self.assertIn("unverified", vc.validation_notes)


if __name__ == "__main__":
    unittest.main()
