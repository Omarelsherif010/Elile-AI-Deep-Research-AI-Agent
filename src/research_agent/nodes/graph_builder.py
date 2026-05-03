from __future__ import annotations

import json
import os
import time
from difflib import SequenceMatcher
from pathlib import Path

import structlog

from research_agent.observability import traceable
from research_agent.schemas import Entity, Relation
from research_agent.state import ResearchState
from research_agent.tools.neo4j_writer import Neo4jWriter

logger = structlog.get_logger()

_ENTITY_MERGE_THRESHOLD = 0.85


@traceable("graph_builder")
def graph_builder(state: ResearchState) -> dict:
    """Canonicalize entities, deduplicate relations, export graph, optionally write to Neo4j."""
    t0 = time.time()
    entities: list[Entity] = state.get("entities", [])
    relations: list[Relation] = state.get("relations", [])
    run_id: str = state.get("run_id", "unknown")

    canonical_entities = _canonicalize_entities(entities)
    entity_map: dict[str, Entity] = {e.id: e for e in canonical_entities}
    deduped_relations = _dedup_relations(relations, entity_map)

    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    graph_export = {
        "entities": [e.model_dump(mode="json") for e in canonical_entities],
        "relations": [r.model_dump(mode="json") for r in deduped_relations],
    }
    (run_dir / "graph_export.json").write_text(json.dumps(graph_export, indent=2, default=str))

    neo4j = Neo4jWriter(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
    )
    if neo4j.is_available():
        stats = neo4j.write_graph(canonical_entities, deduped_relations, entity_map)
        logger.info("neo4j_write_complete", **stats)
        neo4j.close()
    else:
        logger.info("graph_builder_neo4j_skipped_unavailable")

    latency_ms = (time.time() - t0) * 1000
    logger.info(
        "graph_builder_complete",
        entities=len(canonical_entities),
        relations=len(deduped_relations),
        latency_ms=latency_ms,
    )

    return {"entities": canonical_entities, "relations": deduped_relations}


def _canonicalize_entities(entities: list[Entity]) -> list[Entity]:
    """Merge entities with similar names and same type into canonical representatives."""
    if not entities:
        return []
    canonical: list[Entity] = []
    for entity in entities:
        merged = False
        for existing in canonical:
            if existing.type == entity.type:
                similarity = SequenceMatcher(
                    None,
                    existing.canonical_name.lower(),
                    entity.canonical_name.lower(),
                ).ratio()
                if similarity > _ENTITY_MERGE_THRESHOLD:
                    if entity.canonical_name not in existing.aliases:
                        existing.aliases.append(entity.canonical_name)
                    existing.attributes.update(entity.attributes)
                    merged = True
                    break
        if not merged:
            canonical.append(entity)
    return canonical


def _dedup_relations(relations: list[Relation], entity_map: dict[str, Entity]) -> list[Relation]:
    """Deduplicate relations by (subject_entity_id, predicate, object_entity_id) key."""
    seen: dict[tuple[str, str, str], Relation] = {}
    for rel in relations:
        key = (rel.subject_entity_id, rel.predicate, rel.object_entity_id)
        if key not in seen:
            seen[key] = rel
        else:
            existing = seen[key]
            merged_ids = list(set(existing.evidence_claim_ids + rel.evidence_claim_ids))
            existing.evidence_claim_ids = merged_ids
    return list(seen.values())
