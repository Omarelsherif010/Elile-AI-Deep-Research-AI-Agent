from __future__ import annotations

import json
import re
import time
from pathlib import Path

import structlog

from research_agent.confidence import compute_confidence
from research_agent.observability import traceable
from research_agent.schemas import Claim, Source, ValidatedClaim
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


@traceable("validator")
def validator(state: ResearchState) -> dict:
    """Cross-reference claims, classify source tiers, compute confidence scores."""
    t0 = time.time()
    prior_validated: list[ValidatedClaim] = state.get("validated_claims", [])
    prior_validated_ids: set[str] = {vc.id for vc in prior_validated}
    new_claims: list[Claim] = [
        c for c in state.get("claims", []) if c.id not in prior_validated_ids
    ]

    if not new_claims:
        return {}

    all_sources: list[Source] = state.get("sources", [])
    prompt_template = Prompt(_PROMPTS_DIR / "validator.md")

    claims_json = [c.model_dump(mode="json") for c in new_claims[:20]]
    sources_json = [s.model_dump(mode="json") for s in all_sources[:50]]

    prompt_text = prompt_template.render(
        claims_to_validate=str(claims_json),
        all_sources=str(sources_json),
        prior_validated_claims=str([v.model_dump(mode="json") for v in prior_validated[:10]]),
        target_name=state["target"].name,
    )

    validations = _call_validator_llm(prompt_text)
    validation_map = _build_validation_map(validations)

    new_validated: list[ValidatedClaim] = []
    for claim in new_claims:
        v = validation_map.get(claim.id)
        n_domains, max_tier, is_timeless, months_old, contradictions_max_tier, notes = (
            _extract_validation_params(v)
        )

        confidence = compute_confidence(
            max_tier=max_tier,
            n_independent_domains=n_domains,
            is_timeless=is_timeless,
            months_old=months_old,
            contradictions_max_tier=contradictions_max_tier,
        )

        if confidence > 0.5 and n_domains < 2 and max_tier > 1:
            confidence = min(confidence, 0.49)
            notes += " [capped: insufficient corroboration for >0.5]"

        # Constitution Principle 2: label LLM-only claims (≤0.4) and any claim
        # with insufficient corroboration (fewer than 2 independent domains and
        # no Tier-1 source).
        if confidence <= 0.4 or (n_domains < 2 and max_tier > 1):
            notes += " [inferred, unverified: insufficient evidence]"

        new_validated.append(
            ValidatedClaim(
                **claim.model_dump(),
                confidence=confidence,
                supporting_sources=[s for s in all_sources if s.url in claim.source_urls],
                validation_notes=notes,
            )
        )

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "validator_complete",
        new_validated=len(new_validated),
        latency_ms=latency_ms,
    )

    return {"validated_claims": prior_validated + new_validated}


def _call_validator_llm(prompt_text: str) -> list:
    """Call the validator LLM and return raw validation list."""
    try:
        result_raw, _, _ = _router.call("validator", prompt_text)
        if isinstance(result_raw, str):
            match = re.search(r"\{.*\}", result_raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get("validations", [])
            return []
        if hasattr(result_raw, "validations"):
            return list(result_raw.validations)
        return []
    except Exception as exc:
        logger.warning("validator_llm_failed", error=str(exc))
        return []


def _build_validation_map(validations: list) -> dict[str, object]:
    """Build a claim_id → validation dict from the raw list."""
    result: dict[str, object] = {}
    for v in validations:
        if isinstance(v, dict):
            claim_id = v.get("claim_id")
        elif hasattr(v, "claim_id"):
            claim_id = v.claim_id
        else:
            continue
        if claim_id:
            result[claim_id] = v
    return result


def _safe_int(val: object, default: int) -> int:
    """Convert a value to int, returning default on any failure."""
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _extract_validation_params(
    v: object,
) -> tuple[int, int, bool, int, int | None, str]:
    """Extract scoring parameters from a validation entry, with safe defaults."""
    defaults = (1, 4, True, 0, None, "Defaulted: no validator response")
    if v is None:
        return defaults

    if isinstance(v, dict):
        n_domains = _safe_int(v.get("n_independent_domains"), 1)
        tier_assignments: dict = v.get("source_tier_assignments", {})
        if tier_assignments:
            tiers = [_safe_int(t, 4) for t in tier_assignments.values()]
            max_tier = min(tiers) if tiers else 4
        else:
            max_tier = 4
        is_timeless = bool(v.get("is_timeless", True))
        months_old = _safe_int(v.get("months_old"), 0)
        contradictions_max_tier = v.get("contradictions_max_tier")
        if contradictions_max_tier is not None and contradictions_max_tier != "":
            contradictions_max_tier = _safe_int(contradictions_max_tier, None)
        else:
            contradictions_max_tier = None
        notes = str(v.get("validation_notes", ""))
        return n_domains, max_tier, is_timeless, months_old, contradictions_max_tier, notes

    return defaults
