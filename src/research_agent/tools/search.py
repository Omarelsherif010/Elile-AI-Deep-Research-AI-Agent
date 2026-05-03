from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from research_agent.errors import ProviderUnavailable
from research_agent.schemas import SearchResult

logger = structlog.get_logger()


class SearchRouter:
    """Route search queries to the appropriate provider."""

    INTENT_MAP: dict[str, str] = {
        "news": "brave",
        "biographical": "brave",
        "professional": "brave",
        "semantic": "exa",
        "connected": "exa",
        "similar": "exa",
        "content": "firecrawl",
    }

    def __init__(self, cache: SearchCache | None = None) -> None:
        self._cache = cache
        self._brave_key = os.getenv("BRAVE_API_KEY")
        self._exa_key = os.getenv("EXA_API_KEY")
        self._firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        self._tavily_key = os.getenv("TAVILY_API_KEY")

    def route(self, query: str, intent: str = "biographical") -> str:
        """Determine which provider to use for this intent."""
        return self.INTENT_MAP.get(intent, "brave")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def search(
        self,
        query: str,
        intent: str = "biographical",
        n: int = 10,
    ) -> list[SearchResult]:
        """Execute search, checking cache first, falling back on provider failure."""
        provider = self.route(query, intent)

        if self._cache:
            cached = self._cache.get(provider, query, intent)
            if cached:
                logger.info("search_cache_hit", provider=provider, query=query)
                return cached

        try:
            results = await self._dispatch(provider, query, n)
        except (ProviderUnavailable, Exception) as exc:
            logger.warning("search_provider_failed", provider=provider, error=str(exc))
            # Try fallback
            fallback = "brave" if provider != "brave" else "tavily"
            results = await self._dispatch(fallback, query, n)

        if self._cache and results:
            self._cache.set(provider, query, results, intent)
        return results

    async def _dispatch(self, provider: str, query: str, n: int) -> list[SearchResult]:
        """Dispatch to the specific provider."""
        if provider == "brave":
            return await self._search_brave(query, n)
        elif provider == "exa":
            return await self._search_exa(query, n)
        elif provider == "firecrawl":
            return await self._search_firecrawl(query, n)
        elif provider == "tavily":
            return await self._search_tavily(query, n)
        raise ProviderUnavailable(provider, "Unknown provider")

    async def _search_brave(self, query: str, n: int) -> list[SearchResult]:
        if not self._brave_key:
            raise ProviderUnavailable("brave", "BRAVE_API_KEY not set")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._brave_key,
                },
                params={"q": query, "count": n},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                SearchResult(
                    url=item["url"],
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                    retrieved_at=datetime.now(UTC),
                    provider="brave",
                )
            )
        return results

    async def _search_exa(self, query: str, n: int) -> list[SearchResult]:
        if not self._exa_key:
            raise ProviderUnavailable("exa", "EXA_API_KEY not set")
        from exa_py import Exa

        exa = Exa(api_key=self._exa_key)
        result = await asyncio.to_thread(exa.search, query, num_results=n)
        results = []
        for item in result.results:
            results.append(
                SearchResult(
                    url=item.url,
                    title=item.title or "",
                    snippet=item.text[:500] if item.text else "",
                    retrieved_at=datetime.now(UTC),
                    provider="exa",
                )
            )
        return results

    async def _search_firecrawl(self, query: str, n: int) -> list[SearchResult]:
        if not self._firecrawl_key:
            raise ProviderUnavailable("firecrawl", "FIRECRAWL_API_KEY not set")
        from firecrawl import FirecrawlApp

        app = FirecrawlApp(api_key=self._firecrawl_key)
        result = await asyncio.to_thread(app.search, query, limit=n)
        results = []
        for item in result.get("data", []):
            results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", "") or "",
                    content=item.get("content"),
                    retrieved_at=datetime.now(UTC),
                    provider="firecrawl",
                )
            )
        return results

    async def _search_tavily(self, query: str, n: int) -> list[SearchResult]:
        if not self._tavily_key:
            raise ProviderUnavailable("tavily", "TAVILY_API_KEY not set")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._tavily_key,
                    "query": query,
                    "max_results": n,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    url=item["url"],
                    title=item.get("title", ""),
                    snippet=item.get("content", "")[:500],
                    retrieved_at=datetime.now(UTC),
                    provider="tavily",
                )
            )
        return results


# Avoid circular import — SearchCache is defined in memory.py but referenced here
# via the type annotation string. At runtime callers pass an actual SearchCache instance.
# The TYPE_CHECKING guard keeps mypy happy without a real import.
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from research_agent.memory import SearchCache
