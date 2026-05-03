from __future__ import annotations

import structlog

from research_agent.schemas import Entity, Relation

logger = structlog.get_logger()


class Neo4jWriter:
    """Write entities and relations to a Neo4j graph via idempotent MERGE statements."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize.

        If any param is None/empty, operate in no-op mode (graceful skip).
        When all params are provided, attempt to connect and verify connectivity.
        """
        self._driver = None
        self._available = False

        if not uri or not user or not password:
            logger.info("neo4j_no_credentials_noop_mode")
            return

        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self._driver.verify_connectivity()
            self._available = True
            logger.info("neo4j_connected", uri=uri)
        except Exception as exc:
            logger.warning("neo4j_connection_failed", error=str(exc))
            self._driver = None
            self._available = False

    def is_available(self) -> bool:
        """Return True if a live Neo4j connection is established."""
        return self._available

    def write_entity(self, entity: Entity) -> bool:
        """Write entity via idempotent MERGE. Returns True if written, False if skipped."""
        if not self._available or self._driver is None:
            return False

        cypher = """
        MERGE (e:Entity {id: $id})
        SET e.type = $type, e.canonical_name = $canonical_name,
            e.aliases = $aliases, e.attributes = $attributes, e.confidence = $confidence
        """
        try:
            with self._driver.session() as session:
                session.run(
                    cypher,
                    id=entity.id,
                    type=entity.type.value,
                    canonical_name=entity.canonical_name,
                    aliases=entity.aliases,
                    attributes=str(entity.attributes),
                    confidence=entity.confidence,
                )
            return True
        except Exception as exc:
            logger.warning("neo4j_write_entity_failed", entity_id=entity.id, error=str(exc))
            return False

    def write_relation(self, relation: Relation, subject: Entity, object_: Entity) -> bool:
        """Write relation via idempotent MERGE. Returns True if written, False if skipped."""
        if not self._available or self._driver is None:
            return False

        cypher = """
        MATCH (s:Entity {id: $subject_id}), (o:Entity {id: $object_id})
        MERGE (s)-[r:RELATION {predicate: $predicate}]->(o)
        SET r.attributes = $attributes, r.confidence = $confidence,
            r.evidence_claim_ids = $evidence_claim_ids
        """
        try:
            with self._driver.session() as session:
                session.run(
                    cypher,
                    subject_id=subject.id,
                    object_id=object_.id,
                    predicate=relation.predicate,
                    attributes=str(relation.attributes),
                    confidence=relation.confidence,
                    evidence_claim_ids=relation.evidence_claim_ids,
                )
            return True
        except Exception as exc:
            logger.warning(
                "neo4j_write_relation_failed",
                subject_id=subject.id,
                object_id=object_.id,
                error=str(exc),
            )
            return False

    def write_graph(
        self,
        entities: list[Entity],
        relations: list[Relation],
        entity_map: dict[str, Entity],
    ) -> dict:
        """Write all entities and relations. Returns stats dict."""
        entities_written = 0
        entities_skipped = 0
        relations_written = 0
        relations_skipped = 0

        for entity in entities:
            if self.write_entity(entity):
                entities_written += 1
            else:
                entities_skipped += 1

        for relation in relations:
            subject = entity_map.get(relation.subject_entity_id)
            object_ = entity_map.get(relation.object_entity_id)
            if subject is None or object_ is None:
                logger.warning(
                    "neo4j_relation_missing_entity",
                    subject_id=relation.subject_entity_id,
                    object_id=relation.object_entity_id,
                )
                relations_skipped += 1
                continue
            if self.write_relation(relation, subject, object_):
                relations_written += 1
            else:
                relations_skipped += 1

        return {
            "entities_written": entities_written,
            "entities_skipped": entities_skipped,
            "relations_written": relations_written,
            "relations_skipped": relations_skipped,
        }

    def close(self) -> None:
        """Close the Neo4j driver connection if open."""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._available = False
