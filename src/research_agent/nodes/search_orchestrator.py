from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from research_agent.observability import traceable
from research_agent.schemas import Budget, ResearchPlan, SearchTurn, SubQuestion
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt
from research_agent.tools.search import SearchRouter

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

DIMENSION_INTENT: dict[str, str] = {
    "biographical": "biographical",
    "professional_history": "professional",
    "financial_connections": "biographical",
    "network": "semantic",
    "public_statements": "news",
    "risk_surface": "news",
}


@traceable("search_orchestrator")
async def search_orchestrator(state: ResearchState) -> dict:
    """Expand queries and dispatch to search providers."""
    plan: ResearchPlan | None = state.get("plan")
    if not plan:
        return {}

    budget: Budget = state["budget"]
    iteration: int = state.get("iteration", 1)

    search_router = SearchRouter()
    prompt_template = Prompt(_PROMPTS_DIR / "query_expander.md")
    new_turns: list[SearchTurn] = []
    calls_used = 0

    sorted_questions = sorted(plan.sub_questions, key=lambda x: x.priority)

    for sq in sorted_questions:
        remaining_calls = budget.max_search_calls - budget.used_search_calls - calls_used
        if remaining_calls <= 0:
            logger.warning("search_budget_exhausted")
            break

        queries = _expand_queries(sq, state, prompt_template)

        intent = DIMENSION_INTENT.get(sq.dimension, "biographical")

        for query in queries[: min(len(queries), remaining_calls)]:
            try:
                results = await search_router.search(query, intent=intent)
                new_turns.append(
                    SearchTurn(
                        iteration=iteration,
                        query=query,
                        provider=results[0].provider if results else "unknown",
                        results=results,
                    )
                )
                calls_used += 1
            except Exception as exc:
                logger.warning("search_failed", query=query, error=str(exc))

    new_budget = Budget(
        **{
            **budget.model_dump(),
            "used_search_calls": budget.used_search_calls + calls_used,
        }
    )

    logger.info(
        "search_orchestrator_complete",
        iteration=iteration,
        new_turns=len(new_turns),
        calls_used=calls_used,
    )

    return {
        "search_turns": state.get("search_turns", []) + new_turns,
        "budget": new_budget,
    }


def _expand_queries(
    sq: SubQuestion,
    state: ResearchState,
    prompt_template: Prompt,
) -> list[str]:
    """Expand a sub-question into up to 3 search queries using the query_expander LLM."""
    target = state["target"]
    try:
        prompt_text = prompt_template.render(
            sub_question=sq.question,
            target_name=target.name,
            target_context=target.role or "",
            prior_queries="",
        )
        expansion, _, _ = _router.call("query_expander", prompt_text)
        if isinstance(expansion, str):
            match = re.search(r"\{.*\}", expansion, re.DOTALL)
            if match:
                data = json.loads(match.group())
                queries = data.get("queries", [sq.initial_query])[:3]
                if queries:
                    return queries
    except Exception as exc:
        logger.warning("query_expansion_failed", sq_id=sq.id, error=str(exc))
    return [sq.initial_query]
