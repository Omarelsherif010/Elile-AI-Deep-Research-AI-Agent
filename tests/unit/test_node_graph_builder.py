from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_agent.schemas import Entity, EntityType, Relation, TargetProfile
from research_agent.state import ResearchState, create_initial_state


def _make_state(**overrides) -> ResearchState:
    target = TargetProfile(name="Jane Doe", role="CEO", organization="Acme Corp")
    state = create_initial_state(target=target, run_id="test-run-graph")
    state.update(overrides)
    return state


def _make_entity(name: str = "Jane Doe", etype: EntityType = EntityType.PERSON) -> Entity:
    return Entity(
        type=etype,
        canonical_name=name,
        confidence=0.9,
    )


def _make_relation(subject_id: str, object_id: str, predicate: str = "works_at") -> Relation:
    return Relation(
        subject_entity_id=subject_id,
        predicate=predicate,
        object_entity_id=object_id,
        confidence=0.8,
        evidence_claim_ids=["claim-001"],
    )


class TestNodeGraphBuilder(unittest.TestCase):
    """Unit tests for the graph_builder node."""

    def setUp(self) -> None:
        self._original_dir = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._original_dir)

    def _run_in_tmpdir(self, state: ResearchState) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.graph_builder import graph_builder

            result = graph_builder(state)
            return result

    def test_graph_builder_writes_graph_export_json(self) -> None:
        """graph_builder() should write graph_export.json under runs/{run_id}/."""
        entity = _make_entity()
        state = _make_state(
            run_id="test-graph-write",
            entities=[entity],
            relations=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.graph_builder import graph_builder

            graph_builder(state)

            export_path = Path(tmpdir) / "runs" / "test-graph-write" / "graph_export.json"
            self.assertTrue(export_path.exists())
            data = json.loads(export_path.read_text())
            self.assertIn("entities", data)
            self.assertIn("relations", data)

    def test_canonicalize_entities_merges_similar_names(self) -> None:
        """_canonicalize_entities should merge entities with >0.85 name similarity."""
        from research_agent.nodes.graph_builder import _canonicalize_entities

        e1 = _make_entity("Jane Doe")
        e2 = _make_entity("Jane Doe")
        e2.canonical_name = "Jane Doe"
        e2.id = "entity-002"

        result = _canonicalize_entities([e1, e2])

        self.assertEqual(len(result), 1)
        self.assertIn("Jane Doe", result[0].aliases)

    def test_canonicalize_entities_keeps_dissimilar_names(self) -> None:
        """_canonicalize_entities should not merge entities with low name similarity."""
        from research_agent.nodes.graph_builder import _canonicalize_entities

        e1 = _make_entity("Jane Doe")
        e2 = _make_entity("Elon Musk")

        result = _canonicalize_entities([e1, e2])

        self.assertEqual(len(result), 2)

    def test_dedup_relations_deduplicates_by_key(self) -> None:
        """_dedup_relations should merge duplicate (subj, pred, obj) relations."""
        from research_agent.nodes.graph_builder import _dedup_relations

        e1 = _make_entity("Jane Doe")
        e2 = _make_entity("Acme Corp", EntityType.ORGANIZATION)
        r1 = _make_relation(e1.id, e2.id, "works_at")
        r1.evidence_claim_ids = ["claim-001"]
        r2 = _make_relation(e1.id, e2.id, "works_at")
        r2.evidence_claim_ids = ["claim-002"]

        entity_map = {e1.id: e1, e2.id: e2}
        result = _dedup_relations([r1, r2], entity_map)

        self.assertEqual(len(result), 1)
        self.assertIn("claim-001", result[0].evidence_claim_ids)
        self.assertIn("claim-002", result[0].evidence_claim_ids)

    def test_graph_builder_skips_neo4j_when_uri_not_set(self) -> None:
        """graph_builder() should gracefully skip Neo4j when NEO4J_URI is not set."""
        entity = _make_entity()
        state = _make_state(
            run_id="test-neo4j-skip",
            entities=[entity],
            relations=[],
        )

        with patch.dict(
            os.environ,
            {"NEO4J_URI": "", "NEO4J_USER": "", "NEO4J_PASSWORD": ""},
            clear=False,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                from research_agent.nodes.graph_builder import graph_builder

                result = graph_builder(state)

        self.assertIn("entities", result)

    def test_graph_builder_returns_canonical_entities(self) -> None:
        """graph_builder() should return canonicalized entities in the result dict."""
        e1 = _make_entity("Jane Doe")
        e2 = _make_entity("Jane Doe")
        e2.id = "entity-dup"
        state = _make_state(
            run_id="test-canon",
            entities=[e1, e2],
            relations=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from research_agent.nodes.graph_builder import graph_builder

            result = graph_builder(state)

        self.assertIn("entities", result)
        self.assertEqual(len(result["entities"]), 1)


if __name__ == "__main__":
    unittest.main()
