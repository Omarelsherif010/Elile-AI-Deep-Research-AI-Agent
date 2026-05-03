from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from research_agent.memory import EntityRegistry, SearchCache
from research_agent.schemas import Entity, EntityType, SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(url: str = "https://example.com", provider: str = "brave") -> SearchResult:
    return SearchResult(
        url=url,
        title="Test Title",
        snippet="Test snippet.",
        retrieved_at=datetime.now(UTC),
        provider=provider,
    )


def _make_entity(canonical_name: str = "Jane Doe") -> Entity:
    return Entity(
        type=EntityType.PERSON,
        canonical_name=canonical_name,
        aliases=["J. Doe", "Jane"],
        attributes={},
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# SearchCache
# ---------------------------------------------------------------------------


class TestSearchCacheRoundTrip:
    def test_set_and_get_returns_same_results(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        results = [_make_result("https://a.com"), _make_result("https://b.com")]
        cache.set("brave", "Jane Doe", results)
        retrieved = cache.get("brave", "Jane Doe")
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0].url == "https://a.com"
        assert retrieved[1].url == "https://b.com"
        cache.close()

    def test_get_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        result = cache.get("brave", "nonexistent query")
        assert result is None
        cache.close()

    def test_set_overwrites_existing_entry(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        cache.set("brave", "Jane Doe", [_make_result("https://old.com")])
        cache.set("brave", "Jane Doe", [_make_result("https://new.com")])
        retrieved = cache.get("brave", "Jane Doe")
        assert retrieved is not None
        assert retrieved[0].url == "https://new.com"
        cache.close()

    def test_different_providers_stored_independently(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        cache.set("brave", "Jane Doe", [_make_result("https://brave.com", "brave")])
        cache.set("exa", "Jane Doe", [_make_result("https://exa.com", "exa")])
        brave_result = cache.get("brave", "Jane Doe")
        exa_result = cache.get("exa", "Jane Doe")
        assert brave_result is not None
        assert exa_result is not None
        assert brave_result[0].url == "https://brave.com"
        assert exa_result[0].url == "https://exa.com"
        cache.close()


class TestSearchCacheExpiry:
    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        # Directly insert with a very old timestamp
        key = cache._cache_key("brave", "Jane Doe")
        cache._conn.execute(
            "INSERT OR REPLACE INTO search_cache VALUES (?, ?, ?, ?, ?, ?)",
            (
                key,
                "brave",
                "Jane Doe",
                "[{}]",
                time.time() - (35 * 86400),  # 35 days ago
                30,  # TTL = 30 days → expired
            ),
        )
        cache._conn.commit()
        retrieved = cache.get("brave", "Jane Doe", intent="biographical")
        assert retrieved is None
        cache.close()

    def test_fresh_entry_not_expired(self, tmp_path: Path) -> None:
        cache = SearchCache(tmp_path / "cache.db")
        cache.set("brave", "Jane Doe", [_make_result()])
        retrieved = cache.get("brave", "Jane Doe", intent="biographical")
        assert retrieved is not None
        cache.close()

    def test_news_ttl_is_shorter(self) -> None:
        assert SearchCache.NEWS_TTL_DAYS < SearchCache.BIOGRAPHICAL_TTL_DAYS


class TestSearchCacheDeterministicKey:
    def test_same_query_same_key(self) -> None:
        key1 = SearchCache._cache_key("brave", "Jane Doe")
        key2 = SearchCache._cache_key("brave", "Jane Doe")
        assert key1 == key2

    def test_case_insensitive_query(self) -> None:
        key1 = SearchCache._cache_key("brave", "Jane Doe")
        key2 = SearchCache._cache_key("brave", "jane doe")
        assert key1 == key2

    def test_different_providers_different_keys(self) -> None:
        key1 = SearchCache._cache_key("brave", "Jane Doe")
        key2 = SearchCache._cache_key("exa", "Jane Doe")
        assert key1 != key2

    def test_different_queries_different_keys(self) -> None:
        key1 = SearchCache._cache_key("brave", "Jane Doe")
        key2 = SearchCache._cache_key("brave", "John Smith")
        assert key1 != key2


# ---------------------------------------------------------------------------
# EntityRegistry
# ---------------------------------------------------------------------------


class TestEntityRegistryCanonicalize:
    def test_returns_input_when_not_registered(self) -> None:
        registry = EntityRegistry()
        result = registry.canonicalize("Unknown Person", "PERSON")
        assert result == "Unknown Person"

    def test_returns_canonical_name_after_register(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")
        registry.register(entity)
        result = registry.canonicalize("Jane Doe", "PERSON")
        assert result == "Jane Doe"

    def test_alias_resolves_to_canonical(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")  # aliases: ["J. Doe", "Jane"]
        registry.register(entity)
        result = registry.canonicalize("J. Doe", "PERSON")
        assert result == "Jane Doe"

    def test_case_insensitive_lookup(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")
        registry.register(entity)
        result = registry.canonicalize("JANE DOE", "PERSON")
        assert result == "Jane Doe"


class TestEntityRegistryLookup:
    def test_lookup_returns_none_for_unknown(self) -> None:
        registry = EntityRegistry()
        assert registry.lookup("Unknown") is None

    def test_lookup_by_canonical_name(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")
        registry.register(entity)
        result = registry.lookup("Jane Doe")
        assert result is not None
        assert result.canonical_name == "Jane Doe"

    def test_lookup_by_alias(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")
        registry.register(entity)
        result = registry.lookup("J. Doe")
        assert result is not None
        assert result.canonical_name == "Jane Doe"

    def test_lookup_case_insensitive(self) -> None:
        registry = EntityRegistry()
        entity = _make_entity("Jane Doe")
        registry.register(entity)
        result = registry.lookup("jane doe")
        assert result is not None

    def test_register_multiple_entities(self) -> None:
        registry = EntityRegistry()
        entity_a = _make_entity("Jane Doe")
        entity_b = Entity(
            type=EntityType.ORGANIZATION,
            canonical_name="Acme Corp",
            aliases=["Acme"],
            attributes={},
            confidence=0.8,
        )
        registry.register(entity_a)
        registry.register(entity_b)
        assert registry.lookup("Jane Doe") is not None
        assert registry.lookup("Acme Corp") is not None
        assert registry.lookup("Acme") is not None
