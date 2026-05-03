from __future__ import annotations

import json
import re
import time
from pathlib import Path

import structlog

from research_agent.observability import traceable
from research_agent.schemas import Budget, ResearchPlan, ValidatedClaim
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

_DIMENSIONS = [
    "biographical",
    "professional_history",
    "financial_connections",
    "network",
    "public_statements",
    "risk_surface",
]

_BUDGET_ITER_THRESHOLD = 1
_BUDGET_CALLS_THRESHOLD = 10
_BUDGET_DOLLARS_THRESHOLD = 0.50


@traceable("reflector")
def reflector(state: ResearchState) -> dict:
    """Evaluate progress and decide continue/pivot/terminate."""
    t0 = time.time()
    budget: Budget = state["budget"]
    iteration: int = state.get("iteration", 1)
    validated_claims: list[ValidatedClaim] = state.get("validated_claims", [])
    plan: ResearchPlan | None = state.get("plan")
    gaps: list[str] = state.get("gaps", [])

    remaining_iters = budget.max_iterations - budget.used_iterations
    remaining_calls = budget.max_search_calls - budget.used_search_calls
    remaining_dollars = budget.max_dollars - budget.used_dollars

    if (
        remaining_iters <= _BUDGET_ITER_THRESHOLD
        or remaining_calls <= _BUDGET_CALLS_THRESHOLD
        or remaining_dollars <= _BUDGET_DOLLARS_THRESHOLD
    ):
        reason = (
            f"Budget critical: {remaining_iters} iterations, "
            f"${remaining_dollars:.2f}, {remaining_calls} calls remaining"
        )
        logger.info("reflector_terminate_budget", reason=reason)
        return {
            "terminated": True,
            "termination_reason": reason,
            "gaps": gaps,
        }

    prompt_template = Prompt(_PROMPTS_DIR / "reflector.md")
    claims_summary = f"{len(validated_claims)} validated claims across all iterations"
    coverage_summary = {d: 0 for d in _DIMENSIONS}

    prompt_text = prompt_template.render(
        validated_claims=claims_summary,
        current_plan=str(plan.model_dump(mode="json") if plan else {}),
        open_gaps="\n".join(gaps) if gaps else "None",
        budget=(
            f"used: {budget.used_iterations}/{budget.max_iterations} iter, "
            f"${budget.used_dollars:.2f}/${budget.max_dollars}, "
            f"{budget.used_search_calls}/{budget.max_search_calls} calls"
        ),
        iteration=iteration,
        coverage_summary=str(coverage_summary),
    )

    decision, updated_gaps, termination_reason = _call_reflector_llm(prompt_text, gaps)

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "reflector_complete",
        decision=decision,
        iteration=iteration,
        latency_ms=latency_ms,
    )

    return {
        "terminated": decision == "terminate",
        "termination_reason": termination_reason or "",
        "gaps": updated_gaps,
    }


def _call_reflector_llm(
    prompt_text: str, current_gaps: list[str]
) -> tuple[str, list[str], str | None]:
    """Call the reflector LLM and parse decision/gaps/termination_reason."""
    try:
        result_raw, _, _ = _router.call("reflector", prompt_text)
        if isinstance(result_raw, str):
            match = re.search(r"\{.*\}", result_raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
        elif hasattr(result_raw, "model_dump"):
            data = result_raw.model_dump()
        else:
            data = {}

        decision = str(data.get("decision", "continue"))
        updated_gaps = data.get("updated_gaps", current_gaps)
        termination_reason = data.get("termination_reason")
        return decision, updated_gaps, termination_reason
    except Exception as exc:
        logger.warning("reflector_llm_failed", error=str(exc))
        return "continue", current_gaps, None
