from __future__ import annotations

import json
import re
import time
from pathlib import Path

import structlog

from research_agent.observability import traceable
from research_agent.schemas import Entity, Relation, RiskFlag, ValidatedClaim
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

_RISK_CATEGORIES_DESC = """
REGULATORY: sanctions, regulatory actions, enforcement, lawsuits, SEC/court filings
REPUTATIONAL: negative press, controversies, public disputes, retracted statements
NETWORK: associations with flagged individuals/entities, conflict-of-interest networks
FINANCIAL: unusual financial patterns, bankruptcy, undisclosed conflicts
INCONSISTENCY: contradictory claims across sources for the same fact
COVERAGE_GAP: research dimensions with zero or very few low-confidence claims
OTHER: genuine risks not fitting above (requires justification)
"""


@traceable("risk_analyzer")
def risk_analyzer(state: ResearchState) -> dict:
    """Analyze claims and entity graph for risk patterns; return risk_flags."""
    t0 = time.time()
    validated_claims: list[ValidatedClaim] = state.get("validated_claims", [])
    entities: list[Entity] = state.get("entities", [])
    relations: list[Relation] = state.get("relations", [])

    prompt_template = Prompt(_PROMPTS_DIR / "risk_analyzer.md")

    # Sort by confidence descending so the LLM sees the strongest claims first.
    # Cap at 15 claims to stay within TPM limits on rate-limited orgs (~26K tokens).
    top_claims = sorted(validated_claims, key=lambda c: c.confidence, reverse=True)[:15]
    claims_json = [c.model_dump(mode="json") for c in top_claims]
    entities_json = [e.model_dump(mode="json") for e in entities[:10]]
    relations_json = [r.model_dump(mode="json") for r in relations[:10]]

    claim_stats = _build_claim_statistics(validated_claims)

    prompt_text = prompt_template.render(
        validated_claims=str(claims_json),
        entities=str(entities_json),
        relations=str(relations_json),
        target_name=state["target"].name,
        risk_categories=_RISK_CATEGORIES_DESC,
        claim_statistics=claim_stats,
    )

    risk_flags: list[RiskFlag] = _call_risk_analyzer_llm(prompt_text)

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "risk_analyzer_complete",
        n_flags=len(risk_flags),
        latency_ms=latency_ms,
    )

    return {"risk_flags": risk_flags}


def _call_risk_analyzer_llm(prompt_text: str) -> list[RiskFlag]:
    """Call the risk analyzer LLM and return a list of RiskFlag objects."""
    try:
        result_raw, _, _ = _router.call("risk_analyzer", prompt_text)
        if isinstance(result_raw, str):
            match = re.search(r"\{.*\}", result_raw, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            flags_data = data.get("risk_flags", [])
        elif hasattr(result_raw, "risk_flags"):
            flags_data = list(result_raw.risk_flags)
        else:
            return []

        risk_flags: list[RiskFlag] = []
        for flag_data in flags_data:
            if isinstance(flag_data, RiskFlag):
                risk_flags.append(flag_data)
                continue
            if isinstance(flag_data, dict):
                if flag_data.get("type") == "OTHER" and not flag_data.get("justification"):
                    flag_data["justification"] = "Not provided — flagged for review"
                try:
                    risk_flags.append(RiskFlag.model_validate(flag_data))
                except Exception as exc:
                    logger.warning("risk_flag_validation_failed", error=str(exc))
        return risk_flags

    except Exception as exc:
        logger.warning("risk_analyzer_failed", error=str(exc))
        return []


def _build_claim_statistics(claims: list[ValidatedClaim]) -> str:
    """Build a compact summary of all claims so the LLM can detect coverage gaps
    and inconsistencies even when only a top-N slice is provided in the prompt."""
    total = len(claims)
    if total == 0:
        return "No validated claims."

    high = sum(1 for c in claims if c.confidence >= 0.7)
    medium = sum(1 for c in claims if 0.4 <= c.confidence < 0.7)
    low = sum(1 for c in claims if c.confidence < 0.4)
    with_contradictions = sum(1 for c in claims if c.contradicts)

    predicates: dict[str, int] = {}
    for c in claims:
        predicates[c.predicate] = predicates.get(c.predicate, 0) + 1
    top_predicates = sorted(predicates.items(), key=lambda x: x[1], reverse=True)[:10]

    domains: set[str] = set()
    for c in claims:
        for url in c.source_urls:
            parts = url.split("/")
            if len(parts) > 2:
                domains.add(parts[2])

    return (
        f"Total claims: {total} (showing top 15 by confidence). "
        f"Confidence distribution: {high} high (>=0.7), {medium} medium (0.4-0.7), {low} low (<0.4). "
        f"Claims with contradictions: {with_contradictions}. "
        f"Unique source domains: {len(domains)}. "
        f"Top predicates: {', '.join(f'{p}({n})' for p, n in top_predicates)}."
    )
