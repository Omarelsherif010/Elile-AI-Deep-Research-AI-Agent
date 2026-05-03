from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from research_agent.schemas import (
    Claim,
    Entity,
    EntityType,
    SearchResult,
    SearchTurn,
    TargetProfile,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run")
    state.update(overrides)
    return state


def _make_search_turn(
    iteration: int = 1,
    url: str = "https://example.com/bio",
) -> SearchTurn:
    result = SearchResult(
        url=url,
        title="Jane Doe Bio",
        snippet="Jane Doe is CEO of Acme Corp since 2020.",
        retrieved_at=datetime.now(UTC),
        provider="brave",
    )
    return SearchTurn(iteration=iteration, query="Jane Doe CEO", provider="brave", results=[result])


def _make_claim(source_url: str = "https://example.com/bio") -> Claim:
    return Claim(
        subject="Jane Doe",
        predicate="role",
        object="CEO of Acme Corp",
        source_urls=[source_url],
        extraction_confidence=0.8,
    )


def _make_entity() -> Entity:
    return Entity(
        type=EntityType.PERSON,
        canonical_name="Jane Doe",
        confidence=0.9,
    )


def _make_extraction_json() -> str:
    claim_data = {
        "id": "claim-001",
        "subject": "Jane Doe",
        "predicate": "role",
        "object": "CEO of Acme Corp",
        "source_urls": ["https://example.com/bio"],
        "extraction_confidence": 0.8,
    }
    entity_data = {
        "id": "entity-001",
        "type": "PERSON",
        "canonical_name": "Jane Doe",
        "confidence": 0.9,
    }
    import json

    return json.dumps({"claims": [claim_data], "entities": [entity_data], "relations": []})


class TestNodeExtractor(unittest.TestCase):
    """Unit tests for the extractor node."""

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_extractor_appends_new_claims(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should append new Claim objects to state claims list."""
        mock_router.call.return_value = (_make_extraction_json(), 100, 200)
        mock_guardrails = MagicMock()
        mock_guardrails.filter_pii.side_effect = lambda c: c
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn = _make_search_turn(iteration=1)
        state = _make_state(iteration=1, search_turns=[turn], claims=[])

        from research_agent.nodes.extractor import extractor

        result = extractor(state)

        self.assertIn("claims", result)
        self.assertGreater(len(result["claims"]), 0)
        self.assertIsInstance(result["claims"][0], Claim)

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_filter_pii_called_on_each_claim(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should call filter_pii for each extracted claim."""
        mock_router.call.return_value = (_make_extraction_json(), 100, 200)
        mock_guardrails = MagicMock()
        mock_guardrails.filter_pii.side_effect = lambda c: c
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn = _make_search_turn(iteration=1)
        state = _make_state(iteration=1, search_turns=[turn], claims=[])

        from research_agent.nodes.extractor import extractor

        extractor(state)

        mock_guardrails.filter_pii.assert_called()

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_extraction_errors_are_caught_not_raised(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should catch LLM errors and continue without raising."""
        mock_router.call.side_effect = Exception("LLM error")
        mock_guardrails = MagicMock()
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn = _make_search_turn(iteration=1)
        state = _make_state(iteration=1, search_turns=[turn], claims=[])

        from research_agent.nodes.extractor import extractor

        result = extractor(state)

        self.assertIn("claims", result)
        self.assertEqual(len(result["claims"]), 0)

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_pii_filtered_claims_not_added(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should not add claims that are filtered by filter_pii."""
        mock_router.call.return_value = (_make_extraction_json(), 100, 200)
        mock_guardrails = MagicMock()
        mock_guardrails.filter_pii.return_value = None
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn = _make_search_turn(iteration=1)
        state = _make_state(iteration=1, search_turns=[turn], claims=[])

        from research_agent.nodes.extractor import extractor

        result = extractor(state)

        self.assertEqual(len(result["claims"]), 0)

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_sources_appended_for_each_result(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should create a Source entry for each search result URL."""
        mock_router.call.return_value = (_make_extraction_json(), 100, 200)
        mock_guardrails = MagicMock()
        mock_guardrails.filter_pii.side_effect = lambda c: c
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn = _make_search_turn(iteration=1, url="https://news.example.com/article")
        state = _make_state(iteration=1, search_turns=[turn], sources=[])

        from research_agent.nodes.extractor import extractor

        result = extractor(state)

        self.assertIn("sources", result)
        source_urls = [s.url for s in result["sources"]]
        self.assertIn("https://news.example.com/article", source_urls)

    @patch("research_agent.nodes.extractor.Guardrails")
    @patch("research_agent.nodes.extractor._router")
    def test_only_current_iteration_turns_processed(
        self, mock_router: MagicMock, MockGuardrails: MagicMock
    ) -> None:
        """extractor() should only process search turns from the current iteration."""
        mock_router.call.return_value = (_make_extraction_json(), 100, 200)
        mock_guardrails = MagicMock()
        mock_guardrails.filter_pii.side_effect = lambda c: c
        mock_guardrails.wrap_untrusted_content.return_value = "<source>content</source>"
        MockGuardrails.return_value = mock_guardrails

        turn_iter1 = _make_search_turn(iteration=1)
        turn_iter2 = _make_search_turn(iteration=2, url="https://iter2.example.com")
        state = _make_state(
            iteration=1,
            search_turns=[turn_iter1, turn_iter2],
            claims=[],
        )

        from research_agent.nodes.extractor import extractor

        extractor(state)

        call_count = mock_router.call.call_count
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
