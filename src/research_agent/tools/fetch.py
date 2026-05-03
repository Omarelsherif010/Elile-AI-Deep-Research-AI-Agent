from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import httpx
import structlog
import trafilatura

from research_agent.guardrails import Guardrails

logger = structlog.get_logger()
_guardrails = Guardrails()


async def fetch_url(url: str, timeout: int = 30) -> tuple[str | None, bool]:
    """Fetch URL content. Returns (content_or_none, robots_allowed).

    Checks robots.txt first. If disallowed, returns (None, False).
    Uses trafilatura for content extraction.
    Content is wrapped via guardrails.wrap_untrusted_content().
    """
    robots_allowed = _check_robots(url)
    if not robots_allowed:
        logger.info("fetch_robots_disallowed", url=url)
        return None, False

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        logger.warning("fetch_http_error", url=url, error=str(exc))
        return None, True

    content = _extract_content(html, url)
    if not content:
        logger.info("fetch_no_extractable_content", url=url)
        return None, True

    wrapped = _guardrails.wrap_untrusted_content(url, content)
    return wrapped, True


def _check_robots(url: str) -> bool:
    """Check if the URL is allowed by robots.txt for our user-agent."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True  # allow if robots.txt is unavailable


def _extract_content(html: str, url: str) -> str | None:
    """Extract main content from HTML using trafilatura."""
    result = trafilatura.extract(html, include_comments=False, include_tables=True)
    return result
