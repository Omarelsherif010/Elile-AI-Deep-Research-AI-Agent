from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from research_agent.schemas import (
    Budget,
    ResearchPlan,
    SubQuestion,
    TargetProfile,
)
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run")
    state.update(overrides)
    return state


def _make_plan() -> ResearchPlan:
    sq = SubQuestion(
        id="bio_001",
        dimension="biographical",
        question="Who is Jane Doe?",
        rationale="Disambiguation",
        answer_criteria="LinkedIn profile",
        initial_query="Jane Doe CEO",
        priority=1,
    )
    return ResearchPlan(iteration=1, sub_questions=[sq], plan_notes="")


class TestNodeReflector(unittest.TestCase):
    """Unit tests for the reflector node."""

    def test_reflector_terminates_when_iterations_critical(self) -> None:
        """reflector() should return terminated=True when remaining_iters <= 1."""
        budget = Budget(max_iterations=5, used_iterations=4)
        state = _make_state(budget=budget, iteration=4, plan=_make_plan(), gaps=[])

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertTrue(result["terminated"])
        self.assertIn("Budget critical", result["termination_reason"])

    def test_reflector_terminates_when_calls_critical(self) -> None:
        """reflector() should return terminated=True when remaining_calls <= 10."""
        budget = Budget(max_search_calls=60, used_search_calls=51)
        state = _make_state(budget=budget, iteration=2, plan=_make_plan(), gaps=[])

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertTrue(result["terminated"])

    def test_reflector_terminates_when_dollars_critical(self) -> None:
        """reflector() should return terminated=True when remaining_dollars <= 0.50."""
        budget = Budget(max_dollars=5.0, used_dollars=4.60)
        state = _make_state(budget=budget, iteration=2, plan=_make_plan(), gaps=[])

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertTrue(result["terminated"])

    @patch("research_agent.nodes.reflector._router")
    def test_reflector_continues_with_budget_remaining(self, mock_router: MagicMock) -> None:
        """reflector() should return terminated=False and updated gaps when budget is OK."""
        mock_router.call.return_value = (
            json.dumps(
                {
                    "decision": "continue",
                    "updated_gaps": ["gap1", "gap2"],
                    "termination_reason": None,
                }
            ),
            50,
            100,
        )
        budget = Budget(
            max_iterations=8,
            used_iterations=2,
            max_search_calls=60,
            used_search_calls=10,
            max_dollars=5.0,
            used_dollars=0.50,
        )
        state = _make_state(
            budget=budget,
            iteration=2,
            plan=_make_plan(),
            gaps=["original gap"],
        )

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertFalse(result["terminated"])
        self.assertIn("gap1", result["gaps"])

    @patch("research_agent.nodes.reflector._router")
    def test_reflector_llm_failure_defaults_to_continue(self, mock_router: MagicMock) -> None:
        """reflector() should default to continue when LLM call fails."""
        mock_router.call.side_effect = Exception("LLM unavailable")
        budget = Budget(
            max_iterations=8,
            used_iterations=2,
            max_search_calls=60,
            used_search_calls=10,
            max_dollars=5.0,
            used_dollars=0.50,
        )
        state = _make_state(
            budget=budget,
            iteration=2,
            plan=_make_plan(),
            gaps=["original gap"],
        )

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertFalse(result["terminated"])
        self.assertEqual(result["gaps"], ["original gap"])

    @patch("research_agent.nodes.reflector._router")
    def test_reflector_terminate_decision_from_llm(self, mock_router: MagicMock) -> None:
        """reflector() should respect a 'terminate' decision from the LLM."""
        mock_router.call.return_value = (
            json.dumps(
                {
                    "decision": "terminate",
                    "updated_gaps": [],
                    "termination_reason": "All questions answered",
                }
            ),
            50,
            100,
        )
        budget = Budget(
            max_iterations=8,
            used_iterations=2,
            max_search_calls=60,
            used_search_calls=10,
            max_dollars=5.0,
            used_dollars=0.50,
        )
        state = _make_state(
            budget=budget,
            iteration=2,
            plan=_make_plan(),
            gaps=[],
        )

        from research_agent.nodes.reflector import reflector

        result = reflector(state)

        self.assertTrue(result["terminated"])
        self.assertEqual(result["termination_reason"], "All questions answered")


if __name__ == "__main__":
    unittest.main()
