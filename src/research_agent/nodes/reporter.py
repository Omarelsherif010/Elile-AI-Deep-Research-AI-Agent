from __future__ import annotations

import json
import time
from pathlib import Path

import structlog

from research_agent.errors import GuardrailViolation
from research_agent.guardrails import Guardrails
from research_agent.observability import traceable
from research_agent.risk_taxonomy import SEVERITY_ORDER
from research_agent.schemas import (
    Budget,
    Entity,
    Relation,
    RiskFlag,
    TargetProfile,
    ValidatedClaim,
)
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


@traceable("reporter")
def reporter(state: ResearchState) -> dict:
    """Generate report.md and report.json. Apply final output safety check."""
    t0 = time.time()
    run_id: str = state.get("run_id", "unknown")
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    target: TargetProfile = state["target"]
    validated_claims: list[ValidatedClaim] = state.get("validated_claims", [])
    risk_flags: list[RiskFlag] = state.get("risk_flags", [])
    entities: list[Entity] = state.get("entities", [])
    relations: list[Relation] = state.get("relations", [])
    budget: Budget = state["budget"]

    sorted_flags = sorted(
        risk_flags,
        key=lambda f: SEVERITY_ORDER.get(f.severity, 0),
        reverse=True,
    )

    report_markdown = _generate_markdown(
        state, target, validated_claims, sorted_flags, entities, relations, budget, run_id
    )

    report_json = {
        "run_id": run_id,
        "target": target.model_dump(mode="json"),
        "claim_count": len(validated_claims),
        "risk_flag_count": len(risk_flags),
        "risk_flags": [f.model_dump(mode="json") for f in sorted_flags],
        "claims": [c.model_dump(mode="json") for c in validated_claims],
        "budget_used": budget.model_dump(mode="json"),
        "entities": [e.model_dump(mode="json") for e in entities],
        "relations": [r.model_dump(mode="json") for r in relations],
    }

    (run_dir / "report.md").write_text(report_markdown, encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps(report_json, indent=2, default=str), encoding="utf-8"
    )

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "reporter_complete",
        run_id=run_id,
        claims=len(validated_claims),
        flags=len(risk_flags),
        latency_ms=latency_ms,
    )

    return {}


def _generate_markdown(
    state: ResearchState,
    target: TargetProfile,
    validated_claims: list[ValidatedClaim],
    sorted_flags: list[RiskFlag],
    entities: list[Entity],
    relations: list[Relation],
    budget: Budget,
    run_id: str,
) -> str:
    """Generate the report Markdown via LLM, with guardrail check and fallback."""
    prompt_template = Prompt(_PROMPTS_DIR / "reporter.md")

    # Sort by confidence descending so the LLM sees strongest evidence first.
    # Cap at 15 claims to stay within TPM limits on rate-limited orgs (~26K tokens).
    # report.json retains the full claim inventory; the LLM synthesizes from the top slice.
    top_claims = sorted(validated_claims, key=lambda c: c.confidence, reverse=True)[:15]
    prompt_text = prompt_template.render(
        target_name=target.name,
        target_profile=str(target.model_dump(mode="json")),
        validated_claims=str([c.model_dump(mode="json") for c in top_claims]),
        total_claims=len(validated_claims),
        risk_flags=str([f.model_dump(mode="json") for f in sorted_flags]),
        entities=str([e.model_dump(mode="json") for e in entities[:10]]),
        relations=str([r.model_dump(mode="json") for r in relations[:8]]),
        budget_used=(
            f"search_calls={budget.used_search_calls}, "
            f"iterations={budget.used_iterations}"
        ),
        run_id=run_id,
        iterations_run=budget.used_iterations,
    )

    try:
        result_raw, tokens_in, tokens_out = _router.call("reporter", prompt_text, max_tokens=8192)

        if isinstance(result_raw, str):
            try:
                parsed = json.loads(result_raw)
                if isinstance(parsed, dict) and isinstance(parsed.get("markdown"), str):
                    report_markdown = parsed["markdown"]
                else:
                    report_markdown = result_raw
            except json.JSONDecodeError:
                report_markdown = result_raw
        elif hasattr(result_raw, "markdown"):
            report_markdown = str(result_raw.markdown)
        else:
            report_markdown = str(result_raw)

        guardrails = Guardrails()
        report_markdown = guardrails.check_output_safety(report_markdown)
        return report_markdown

    except GuardrailViolation as exc:
        logger.error("reporter_guardrail_violation", error=str(exc))
        return _fallback_report(state)
    except Exception as exc:
        logger.error("reporter_failed", error=str(exc))
        return _fallback_report(state)


def _fallback_report(state: ResearchState) -> str:
    """Minimal fallback report when LLM or guardrail fails."""
    target = state["target"]
    vclaims = state.get("validated_claims", [])
    return (
        f"# Research Report: {target.name}\n\n"
        "## Scope and Limitations\n"
        "This report was generated with limited LLM output. "
        "Public sources only. No sensitive attribute inference.\n\n"
        "## Findings\n"
        f"{len(vclaims)} validated claims were collected. "
        "See report.json for full claim inventory.\n\n"
        "## Coverage Gaps\n"
        "Report generation encountered an error. Raw claims are in report.json.\n"
    )
