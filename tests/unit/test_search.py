from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from research_agent.schemas import SearchResult
from research_agent.tools.search import SearchRouter

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


def _brave_response_payload(n: int = 2) -> dict:
    return {
        "web": {
            "results": [
                {
                    "url": f"https://example.com/{i}",
                    "title": f"Result {i}",
                    "description": f"Snippet {i}",
                }
                for i in range(n)
            ]
        }
    }


def _tavily_response_payload(n: int = 2) -> dict:
    return {
        "results": [
            {
                "url": f"https://tavily.com/{i}",
                "title": f"Tavily Result {i}",
                "content": f"Tavily snippet {i}",
            }
            for i in range(n)
        ]
    }


# ---------------------------------------------------------------------------
# route()
# ---------------------------------------------------------------------------


class TestRoute:
    def test_news_routes_to_brave(self) -> None:
        router = SearchRouter()
        assert router.route("query", "news") == "brave"

    def test_biographical_routes_to_brave(self) -> None:
        router = SearchRouter()
        assert router.route("query", "biographical") == "brave"

    def test_professional_routes_to_brave(self) -> None:
        router = SearchRouter()
        assert router.route("query", "professional") == "brave"

    def test_semantic_routes_to_exa(self) -> None:
        router = SearchRouter()
        assert router.route("query", "semantic") == "exa"

    def test_connected_routes_to_exa(self) -> None:
        router = SearchRouter()
        assert router.route("query", "connected") == "exa"

    def test_similar_routes_to_exa(self) -> None:
        router = SearchRouter()
        assert router.route("query", "similar") == "exa"

    def test_content_routes_to_firecrawl(self) -> None:
        router = SearchRouter()
        assert router.route("query", "content") == "firecrawl"

    def test_unknown_intent_defaults_to_brave(self) -> None:
        router = SearchRouter()
        assert router.route("query", "mystery_intent") == "brave"


# ---------------------------------------------------------------------------
# search() — cache hit
# ---------------------------------------------------------------------------


class TestSearchCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_results_without_calling_provider(self) -> None:
        cached = [_make_result("https://cached.com", "brave")]
        mock_cache = MagicMock()
        mock_cache.get.return_value = cached

        router = SearchRouter(cache=mock_cache)
        results = await router.search("Jane Doe", intent="biographical")

        assert results == cached
        mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_provider_when_cache_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")  # must precede router construction
        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # cache miss
        mock_cache.set = MagicMock()

        router = SearchRouter(cache=mock_cache)

        with respx.mock:
            respx.get("https://api.search.brave.com/res/v1/web/search").mock(
                return_value=httpx.Response(200, json=_brave_response_payload(1))
            )
            results = await router.search("Jane Doe", intent="biographical")

        assert len(results) == 1
        mock_cache.set.assert_called_once()


# ---------------------------------------------------------------------------
# search() — Brave provider
# ---------------------------------------------------------------------------


class TestSearchBrave:
    @pytest.mark.asyncio
    async def test_returns_search_result_objects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        router = SearchRouter()

        with respx.mock:
            respx.get("https://api.search.brave.com/res/v1/web/search").mock(
                return_value=httpx.Response(200, json=_brave_response_payload(3))
            )
            results = await router.search("Jane Doe", intent="news")

        assert len(results) == 3
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.provider == "brave"

    @pytest.mark.asyncio
    async def test_brave_result_fields_populated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        router = SearchRouter()

        with respx.mock:
            respx.get("https://api.search.brave.com/res/v1/web/search").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "web": {
                            "results": [
                                {
                                    "url": "https://news.example.com/article",
                                    "title": "Jane Doe CEO",
                                    "description": "Jane Doe was appointed CEO.",
                                }
                            ]
                        }
                    },
                )
            )
            results = await router.search("Jane Doe", intent="news")

        assert results[0].url == "https://news.example.com/article"
        assert results[0].title == "Jane Doe CEO"
        assert "appointed" in results[0].snippet


# ---------------------------------------------------------------------------
# search() — fallback
# ---------------------------------------------------------------------------


class TestSearchFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_tavily_when_brave_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")

        router = SearchRouter()
        # Patch tenacity so we don't wait on retries
        with patch.object(router, "_search_brave", side_effect=Exception("brave down")):
            with respx.mock:
                respx.post("https://api.tavily.com/search").mock(
                    return_value=httpx.Response(200, json=_tavily_response_payload(2))
                )
                results = await router.search("Jane Doe", intent="biographical")

        assert len(results) == 2
        assert all(r.provider == "tavily" for r in results)

    @pytest.mark.asyncio
    async def test_exa_falls_back_to_brave(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "brave-key")

        router = SearchRouter()
        with patch.object(router, "_search_exa", side_effect=Exception("exa down")):
            with respx.mock:
                respx.get("https://api.search.brave.com/res/v1/web/search").mock(
                    return_value=httpx.Response(200, json=_brave_response_payload(1))
                )
                results = await router.search("Jane Doe", intent="semantic")

        assert len(results) == 1
        assert results[0].provider == "brave"
