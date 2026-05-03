from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import structlog

from research_agent.guardrails import Guardrails
from research_agent.observability import traceable
from research_agent.schemas import (
    Claim,
    Entity,
    Relation,
    SearchResult,
    SearchTurn,
    Source,
)
from research_agent.state import ResearchState
from research_agent.tools.llm import LLMRouter, Prompt

logger = structlog.get_logger()

_router = LLMRouter()
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


@traceable("extractor")
def extractor(state: ResearchState) -> dict:
    """Extract claims, entities, and relations from the latest search results."""
    t0 = time.time()
    iteration: int = state.get("iteration", 1)
    search_turns: list[SearchTurn] = [
        t for t in state.get("search_turns", []) if t.iteration == iteration
    ]
    prior_claims: list[Claim] = state.get("claims", [])

    guardrails = Guardrails()
    prompt_template = Prompt(_PROMPTS_DIR / "extractor.md")

    new_claims: list[Claim] = []
    new_entities: list[Entity] = []
    new_relations: list[Relation] = []
    new_sources: list[Source] = []

    all_results: list[SearchResult] = [r for turn in search_turns for r in turn.results]

    for result in all_results:
        content = result.content or result.snippet
        wrapped = guardrails.wrap_untrusted_content(result.url, content)

        domain = urlparse(result.url).netloc
        source = Source(
            url=result.url,
            domain=domain,
            tier=3,
            retrieved_at=result.retrieved_at,
            robots_allowed=True,
        )
        new_sources.append(source)

        prior_summary = [(c.subject, c.predicate) for c in prior_claims[-10:]]
        try:
            prompt_text = prompt_template.render(
                target_name=state["target"].name,
                target_context=state["target"].role or "",
                search_results=f"[{wrapped}]",
                prior_claim_subjects_predicates=str(prior_summary),
            )
        except Exception as exc:
            logger.warning("extractor_prompt_render_failed", url=result.url, error=str(exc))
            continue

        try:
            result_raw, tokens_in, tokens_out = _router.call("extractor", prompt_text)

            extracted_claims, extracted_entities, extracted_relations = _parse_extraction(
                result_raw
            )

            for claim in extracted_claims:
                filtered = guardrails.filter_pii(claim)
                if filtered:
                    new_claims.append(filtered)

            new_entities.extend(extracted_entities)
            new_relations.extend(extracted_relations)

        except Exception as exc:
            logger.warning("extractor_failed", url=result.url, error=str(exc))

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "extractor_complete",
        iteration=iteration,
        new_claims=len(new_claims),
        new_entities=len(new_entities),
        new_relations=len(new_relations),
        latency_ms=latency_ms,
    )

    return {
        "claims": prior_claims + new_claims,
        "entities": state.get("entities", []) + new_entities,
        "relations": state.get("relations", []) + new_relations,
        "sources": state.get("sources", []) + new_sources,
    }


def _parse_extraction(
    result_raw: object,
) -> tuple[list[Claim], list[Entity], list[Relation]]:
    """Parse the LLM extraction output into typed lists."""
    if hasattr(result_raw, "claims"):
        return (
            list(result_raw.claims),
            list(result_raw.entities),
            list(result_raw.relations),
        )

    if isinstance(result_raw, str):
        match = re.search(r"\{.*\}", result_raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                claims = [Claim.model_validate(c) for c in data.get("claims", [])]
                entities = [Entity.model_validate(e) for e in data.get("entities", [])]
                relations = [Relation.model_validate(r) for r in data.get("relations", [])]
                return claims, entities, relations
            except Exception as exc:
                logger.warning("extraction_parse_failed", error=str(exc))

    return [], [], []
