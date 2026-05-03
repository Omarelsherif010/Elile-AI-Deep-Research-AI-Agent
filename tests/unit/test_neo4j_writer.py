from __future__ import annotations

from unittest.mock import MagicMock

from research_agent.schemas import Entity, EntityType, Relation
from research_agent.tools.neo4j_writer import Neo4jWriter


def _make_entity(canonical_name: str = "Jane Doe") -> Entity:
    return Entity(
        type=EntityType.PERSON,
        canonical_name=canonical_name,
        aliases=["J. Doe"],
        attributes={"role": "CEO"},
        confidence=0.9,
    )


def _make_relation(subject: Entity, object_: Entity) -> Relation:
    return Relation(
        subject_entity_id=subject.id,
        predicate="WORKS_AT",
        object_entity_id=object_.id,
        confidence=0.8,
        evidence_claim_ids=["claim-1"],
    )


class TestNoopMode:
    def test_none_uri_noop(self) -> None:
        writer = Neo4jWriter(uri=None, user="user", password="pass")
        assert writer.is_available() is False

    def test_none_user_noop(self) -> None:
        writer = Neo4jWriter(uri="bolt://localhost", user=None, password="pass")
        assert writer.is_available() is False

    def test_none_password_noop(self) -> None:
        writer = Neo4jWriter(uri="bolt://localhost", user="user", password=None)
        assert writer.is_available() is False

    def test_empty_uri_noop(self) -> None:
        writer = Neo4jWriter(uri="", user="user", password="pass")
        assert writer.is_available() is False

    def test_write_entity_returns_false_when_unavailable(self) -> None:
        writer = Neo4jWriter()
        entity = _make_entity()
        assert writer.write_entity(entity) is False

    def test_write_relation_returns_false_when_unavailable(self) -> None:
        writer = Neo4jWriter()
        subject = _make_entity("Jane")
        obj = _make_entity("Acme")
        relation = _make_relation(subject, obj)
        assert writer.write_relation(relation, subject, obj) is False


class TestWriteEntityWithMockDriver:
    def _make_writer_with_mock(self) -> tuple[Neo4jWriter, MagicMock]:
        """Return a Neo4jWriter with a mock Neo4j driver already injected."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        writer = Neo4jWriter.__new__(Neo4jWriter)
        writer._driver = mock_driver
        writer._available = True
        return writer, mock_session

    def test_write_entity_executes_merge(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        entity = _make_entity()
        result = writer.write_entity(entity)
        assert result is True
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "MERGE" in cypher
        assert "Entity" in cypher

    def test_write_entity_passes_correct_params(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        entity = _make_entity("Alice Smith")
        writer.write_entity(entity)
        kwargs = mock_session.run.call_args[1]
        assert kwargs["id"] == entity.id
        assert kwargs["canonical_name"] == "Alice Smith"
        assert kwargs["confidence"] == entity.confidence

    def test_write_entity_returns_false_on_exception(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        mock_session.run.side_effect = RuntimeError("db error")
        entity = _make_entity()
        result = writer.write_entity(entity)
        assert result is False

    def test_write_relation_executes_merge(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        subject = _make_entity("Jane")
        obj = _make_entity("Acme Corp")
        relation = _make_relation(subject, obj)
        result = writer.write_relation(relation, subject, obj)
        assert result is True
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE" in cypher
        assert "RELATION" in cypher

    def test_write_relation_returns_false_on_exception(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        mock_session.run.side_effect = Exception("timeout")
        subject = _make_entity("Jane")
        obj = _make_entity("Acme")
        relation = _make_relation(subject, obj)
        result = writer.write_relation(relation, subject, obj)
        assert result is False


class TestWriteGraph:
    def _make_writer_with_mock(self) -> tuple[Neo4jWriter, MagicMock]:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        writer = Neo4jWriter.__new__(Neo4jWriter)
        writer._driver = mock_driver
        writer._available = True
        return writer, mock_session

    def test_write_graph_returns_stats(self) -> None:
        writer, _ = self._make_writer_with_mock()
        e1 = _make_entity("Jane")
        e2 = _make_entity("Acme")
        rel = _make_relation(e1, e2)
        entity_map = {e1.id: e1, e2.id: e2}
        stats = writer.write_graph([e1, e2], [rel], entity_map)
        assert stats["entities_written"] == 2
        assert stats["entities_skipped"] == 0
        assert stats["relations_written"] == 1
        assert stats["relations_skipped"] == 0

    def test_write_graph_all_keys_present(self) -> None:
        writer, _ = self._make_writer_with_mock()
        stats = writer.write_graph([], [], {})
        required_keys = {
            "entities_written",
            "entities_skipped",
            "relations_written",
            "relations_skipped",
        }
        assert required_keys == set(stats.keys())

    def test_write_graph_skips_relation_with_missing_entity(self) -> None:
        writer, _ = self._make_writer_with_mock()
        e1 = _make_entity("Jane")
        e2 = _make_entity("Acme")
        rel = _make_relation(e1, e2)
        # entity_map only has e1; e2 is missing
        entity_map = {e1.id: e1}
        stats = writer.write_graph([e1], [rel], entity_map)
        assert stats["relations_skipped"] == 1
        assert stats["relations_written"] == 0

    def test_write_graph_counts_failures_as_skipped(self) -> None:
        writer, mock_session = self._make_writer_with_mock()
        mock_session.run.side_effect = Exception("neo4j down")
        e1 = _make_entity("Jane")
        stats = writer.write_graph([e1], [], {})
        assert stats["entities_skipped"] == 1
        assert stats["entities_written"] == 0

    def test_write_graph_noop_mode(self) -> None:
        writer = Neo4jWriter()  # no-op mode
        e1 = _make_entity("Jane")
        e2 = _make_entity("Acme")
        rel = _make_relation(e1, e2)
        entity_map = {e1.id: e1, e2.id: e2}
        stats = writer.write_graph([e1, e2], [rel], entity_map)
        assert stats["entities_written"] == 0
        assert stats["entities_skipped"] == 2
        assert stats["relations_written"] == 0
        assert stats["relations_skipped"] == 1
