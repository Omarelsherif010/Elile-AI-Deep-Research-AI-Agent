from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from research_agent.schemas import Budget, ResearchPlan, SubQuestion, TargetProfile
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run")
    state.update(overrides)
    return state


def _make_plan(iteration: int = 1) -> ResearchPlan:
    sq = SubQuestion(
        id="bio_001",
        dimension="biographical",
        question="Who is Jane Doe?",
        rationale="Disambiguation",
        answer_criteria="LinkedIn or company bio",
        initial_query="Jane Doe CEO Acme Corp",
        priority=1,
    )
    return ResearchPlan(iteration=iteration, sub_questions=[sq], plan_notes="test plan")


class TestNodePlanner(unittest.TestCase):
    """Unit tests for the planner node."""

    def _make_mock_router(self) -> MagicMock:
        mock_router = MagicMock()
        mock_router.call.return_value = (_make_plan(), 100, 200)
        return mock_router

    @patch("research_agent.nodes.planner._router")
    def test_planner_increments_iteration(self, mock_router: MagicMock) -> None:
        """planner() should increment iteration from 0 to 1."""
        mock_router.call.return_value = (_make_plan(1), 100, 200)
        state = _make_state(iteration=0)

        from research_agent.nodes.planner import planner

        result = planner(state)

        self.assertEqual(result["iteration"], 1)

    @patch("research_agent.nodes.planner._router")
    def test_planner_returns_research_plan(self, mock_router: MagicMock) -> None:
        """planner() should return a dict with key 'plan' of type ResearchPlan."""
        expected_plan = _make_plan(2)
        mock_router.call.return_value = (expected_plan, 100, 200)
        state = _make_state(iteration=1)

        from research_agent.nodes.planner import planner

        result = planner(state)

        self.assertIn("plan", result)
        self.assertIsInstance(result["plan"], ResearchPlan)
        self.assertEqual(result["plan"].sub_questions[0].id, "bio_001")

    @patch("research_agent.nodes.planner._router")
    def test_planner_passes_gaps_to_prompt(self, mock_router: MagicMock) -> None:
        """planner() should include gaps in the rendered prompt text."""
        mock_router.call.return_value = (_make_plan(), 50, 100)
        state = _make_state(
            iteration=0,
            gaps=["Missing financial data", "No risk surface found"],
        )

        from research_agent.nodes.planner import planner

        planner(state)

        call_args = mock_router.call.call_args
        prompt_text: str = call_args[0][1]
        self.assertIn("Missing financial data", prompt_text)
        self.assertIn("No risk surface found", prompt_text)

    @patch("research_agent.nodes.planner._router")
    def test_planner_uses_planner_role(self, mock_router: MagicMock) -> None:
        """planner() should invoke the LLM with the 'planner' role."""
        mock_router.call.return_value = (_make_plan(), 50, 100)
        state = _make_state()

        from research_agent.nodes.planner import planner

        planner(state)

        role_arg = mock_router.call.call_args[0][0]
        self.assertEqual(role_arg, "planner")

    def test_budget_guard_terminates_on_iterations(self) -> None:
        """budget_guard(planner) returns terminated=True when iterations cap is reached.

        The planner node itself no longer raises; the graph.py budget_guard wrapper
        returns a graceful termination dict (Constitution Principle 4).
        """
        from research_agent.graph import budget_guard
        from research_agent.nodes.planner import planner

        state = _make_state()
        state["budget"] = Budget(max_iterations=3, used_iterations=3)

        result = budget_guard(planner)(state)
        self.assertTrue(result.get("terminated"))
        self.assertIn("Iteration", result.get("termination_reason", ""))

    def test_budget_guard_terminates_on_dollars(self) -> None:
        """budget_guard(planner) returns terminated=True when dollar cap is reached."""
        from research_agent.graph import budget_guard
        from research_agent.nodes.planner import planner

        state = _make_state()
        state["budget"] = Budget(max_dollars=5.0, used_dollars=5.0)

        result = budget_guard(planner)(state)
        self.assertTrue(result.get("terminated"))
        self.assertIn("Dollar", result.get("termination_reason", ""))

    @patch("research_agent.nodes.planner._router")
    def test_planner_empty_gaps_renders_none(self, mock_router: MagicMock) -> None:
        """planner() should render 'None' in prompt when gaps list is empty."""
        mock_router.call.return_value = (_make_plan(), 50, 100)
        state = _make_state(gaps=[])

        from research_agent.nodes.planner import planner

        planner(state)

        call_args = mock_router.call.call_args
        prompt_text: str = call_args[0][1]
        self.assertIn("None", prompt_text)


if __name__ == "__main__":
    unittest.main()
