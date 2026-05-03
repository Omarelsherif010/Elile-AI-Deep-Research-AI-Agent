from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from research_agent.schemas import (
    Budget,
    ResearchPlan,
    SearchResult,
    SearchTurn,
    SubQuestion,
    TargetProfile,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run")
    state.update(overrides)
    return state


def _make_sub_question(
    id_: str = "bio_001",
    dimension: str = "biographical",
    priority: int = 1,
    query: str = "Jane Doe CEO",
) -> SubQuestion:
    return SubQuestion(
        id=id_,
        dimension=dimension,
        question="Who is Jane Doe?",
        rationale="Disambiguation",
        answer_criteria="LinkedIn or company bio",
        initial_query=query,
        priority=priority,
    )


def _make_plan(sub_questions: list[SubQuestion] | None = None) -> ResearchPlan:
    sqs = sub_questions or [_make_sub_question()]
    return ResearchPlan(iteration=1, sub_questions=sqs, plan_notes="")


def _make_search_result(url: str = "https://example.com") -> SearchResult:
    return SearchResult(
        url=url,
        title="Test Result",
        snippet="Some content",
        retrieved_at=datetime.now(UTC),
        provider="brave",
    )


class TestNodeSearchOrchestrator(unittest.TestCase):
    """Unit tests for the search_orchestrator node."""

    def _run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("research_agent.nodes.search_orchestrator.SearchRouter")
    @patch("research_agent.nodes.search_orchestrator._router")
    def test_appends_search_turns(
        self, mock_llm_router: MagicMock, MockSearchRouter: MagicMock
    ) -> None:
        """search_orchestrator should append new SearchTurns to state."""
        mock_llm_router.call.return_value = (
            '{"queries": ["Jane Doe CEO Acme"]}',
            10,
            20,
        )
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[_make_search_result()])
        MockSearchRouter.return_value = mock_search

        plan = _make_plan()
        state = _make_state(plan=plan, iteration=1, search_turns=[])

        from research_agent.nodes.search_orchestrator import search_orchestrator

        result = self._run_async(search_orchestrator(state))

        self.assertIn("search_turns", result)
        self.assertGreater(len(result["search_turns"]), 0)
        self.assertIsInstance(result["search_turns"][0], SearchTurn)

    @patch("research_agent.nodes.search_orchestrator.SearchRouter")
    @patch("research_agent.nodes.search_orchestrator._router")
    def test_stops_when_budget_exhausted(
        self, mock_llm_router: MagicMock, MockSearchRouter: MagicMock
    ) -> None:
        """search_orchestrator should stop dispatching when search call budget is exhausted."""
        mock_llm_router.call.return_value = (
            '{"queries": ["q1", "q2", "q3"]}',
            10,
            20,
        )
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[_make_search_result()])
        MockSearchRouter.return_value = mock_search

        sub_questions = [_make_sub_question(id_=f"sq_{i}", priority=i + 1) for i in range(5)]
        plan = _make_plan(sub_questions)
        budget = Budget(max_search_calls=2, used_search_calls=2)
        state = _make_state(plan=plan, iteration=1, search_turns=[], budget=budget)

        from research_agent.nodes.search_orchestrator import search_orchestrator

        result = self._run_async(search_orchestrator(state))

        self.assertEqual(len(result.get("search_turns", [])), 0)

    @patch("research_agent.nodes.search_orchestrator.SearchRouter")
    @patch("research_agent.nodes.search_orchestrator._router")
    def test_falls_back_to_initial_query_on_expansion_failure(
        self, mock_llm_router: MagicMock, MockSearchRouter: MagicMock
    ) -> None:
        """search_orchestrator should use initial_query when query expansion fails."""
        mock_llm_router.call.side_effect = Exception("LLM unavailable")
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[_make_search_result()])
        MockSearchRouter.return_value = mock_search

        sq = _make_sub_question(query="fallback query original")
        plan = _make_plan([sq])
        state = _make_state(plan=plan, iteration=1, search_turns=[])

        from research_agent.nodes.search_orchestrator import search_orchestrator

        result = self._run_async(search_orchestrator(state))

        dispatched_queries = [t.query for t in result.get("search_turns", [])]
        self.assertIn("fallback query original", dispatched_queries)

    @patch("research_agent.nodes.search_orchestrator.SearchRouter")
    @patch("research_agent.nodes.search_orchestrator._router")
    def test_no_plan_returns_empty_dict(
        self, mock_llm_router: MagicMock, MockSearchRouter: MagicMock
    ) -> None:
        """search_orchestrator should return {} when plan is None."""
        state = _make_state(plan=None)

        from research_agent.nodes.search_orchestrator import search_orchestrator

        result = self._run_async(search_orchestrator(state))

        self.assertEqual(result, {})

    @patch("research_agent.nodes.search_orchestrator.SearchRouter")
    @patch("research_agent.nodes.search_orchestrator._router")
    def test_budget_used_search_calls_incremented(
        self, mock_llm_router: MagicMock, MockSearchRouter: MagicMock
    ) -> None:
        """search_orchestrator should increment used_search_calls in budget."""
        mock_llm_router.call.return_value = ('{"queries": ["query1"]}', 10, 20)
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[_make_search_result()])
        MockSearchRouter.return_value = mock_search

        plan = _make_plan()
        budget = Budget(max_search_calls=10, used_search_calls=0)
        state = _make_state(plan=plan, iteration=1, budget=budget)

        from research_agent.nodes.search_orchestrator import search_orchestrator

        result = self._run_async(search_orchestrator(state))

        self.assertIn("budget", result)
        self.assertGreater(result["budget"].used_search_calls, 0)


if __name__ == "__main__":
    unittest.main()
