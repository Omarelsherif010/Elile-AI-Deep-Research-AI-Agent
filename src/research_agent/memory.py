from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from research_agent.schemas import Entity, SearchResult

if TYPE_CHECKING:
    from langgraph.checkpoint.sqlite import SqliteSaver

logger = structlog.get_logger()


class SearchCache:
    """SQLite-backed search result cache with TTL."""

    NEWS_TTL_DAYS = 7
    BIOGRAPHICAL_TTL_DAYS = 30

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT,
                query TEXT,
                results_json TEXT,
                created_at REAL,
                ttl_days INTEGER
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _cache_key(provider: str, query: str) -> str:
        return hashlib.sha256(f"{provider}:{query.lower().strip()}".encode()).hexdigest()

    def get(
        self, provider: str, query: str, intent: str = "biographical"
    ) -> list[SearchResult] | None:
        """Return cached results if present and not expired."""
        key = self._cache_key(provider, query)
        row = self._conn.execute(
            "SELECT results_json, created_at, ttl_days FROM search_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        results_json, created_at, stored_ttl = row
        age_days = (time.time() - created_at) / 86400
        if age_days > stored_ttl:
            return None
        data = json.loads(results_json)
        return [SearchResult.model_validate(r) for r in data]

    def set(
        self,
        provider: str,
        query: str,
        results: list[SearchResult],
        intent: str = "biographical",
    ) -> None:
        """Store results in the cache."""
        key = self._cache_key(provider, query)
        ttl_days = self.NEWS_TTL_DAYS if intent == "news" else self.BIOGRAPHICAL_TTL_DAYS
        results_json = json.dumps([r.model_dump(mode="json") for r in results])
        self._conn.execute(
            "INSERT OR REPLACE INTO search_cache VALUES (?, ?, ?, ?, ?, ?)",
            (key, provider, query, results_json, time.time(), ttl_days),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()


class EntityRegistry:
    """In-memory canonical entity registry (optionally backed by Neo4j for cross-run dedup)."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}  # lower-cased name -> Entity

    def canonicalize(self, name: str, entity_type: str) -> str:
        """Return canonical name for an entity, resolving aliases."""
        key = name.lower().strip()
        if key in self._entities:
            return self._entities[key].canonical_name
        return name

    def register(self, entity: Entity) -> None:
        """Register an entity and all its aliases into the registry."""
        key = entity.canonical_name.lower().strip()
        self._entities[key] = entity
        for alias in entity.aliases:
            self._entities[alias.lower().strip()] = entity

    def lookup(self, name: str) -> Entity | None:
        """Look up an entity by any of its names/aliases."""
        return self._entities.get(name.lower().strip())


class RunStateStore:
    """Thin wrapper around LangGraph SqliteSaver for run state persistence."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_checkpointer(self) -> SqliteSaver:
        """Return a LangGraph SqliteSaver instance."""
        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver.from_conn_string(str(self.db_path))
