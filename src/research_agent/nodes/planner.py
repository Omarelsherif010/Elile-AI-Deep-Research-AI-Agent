from __future__ import annotations

import time
from pathlib import Path

import structlog

from research_agent.observability import traceable
from research_agent.schemas import Budget, ResearchPlan, TargetProfile, ValidatedClaim
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


@traceable("planner")
def planner(state: ResearchState) -> dict:
    """Generate or refine the research plan for this iteration."""
    t0 = time.time()

    target: TargetProfile = state["target"]
    iteration: int = state.get("iteration", 0)
    gaps: list[str] = state.get("gaps", [])
    validated_claims: list[ValidatedClaim] = state.get("validated_claims", [])
    budget: Budget = state["budget"]

    prompt_template = Prompt(_PROMPTS_DIR / "planner.md")
    prior_findings_summary = _summarize_claims(validated_claims)

    target_context = ""
    if target.role and target.organization:
        target_context = f"{target.role} at {target.organization}"
    elif target.role:
        target_context = target.role
    elif target.organization:
        target_context = target.organization

    prompt_text = prompt_template.render(
        target_name=target.name,
        target_context=target_context,
        prior_findings=prior_findings_summary,
        open_gaps="\n".join(gaps) if gaps else "None",
        iteration=iteration + 1,
        remaining_budget=(
            f"iterations: {budget.max_iterations - budget.used_iterations}, "
            f"search_calls: {budget.max_search_calls - budget.used_search_calls}, "
            f"dollars: {budget.max_dollars - budget.used_dollars:.2f}"
        ),
    )

    plan, tokens_in, tokens_out = _router.call("planner", prompt_text, ResearchPlan)
    latency_ms = (time.time() - t0) * 1000

    logger.info(
        "planner_complete",
        iteration=iteration + 1,
        n_questions=len(plan.sub_questions),
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )

    return {
        "plan": plan,
        "iteration": iteration + 1,
    }


def _summarize_claims(validated_claims: list[ValidatedClaim]) -> str:
    """Produce a compact text summary of up to 20 validated claims for the planner prompt."""
    if not validated_claims:
        return "[]"
    lines: list[str] = []
    for vc in validated_claims[:20]:
        lines.append(f"- {vc.subject} {vc.predicate} {vc.object} (confidence={vc.confidence:.2f})")
    return "\n".join(lines)
