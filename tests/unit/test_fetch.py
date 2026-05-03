from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from research_agent.tools import fetch as fetch_module
from research_agent.tools.fetch import fetch_url

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
<article>
<h1>Big News Story</h1>
<p>This is the main body content of the article. It has multiple sentences.
There is plenty of text here for trafilatura to extract successfully.</p>
<p>Second paragraph with more content to make extraction reliable.</p>
</article>
</body>
</html>
"""

_ROBOTS_DISALLOW = b"User-agent: *\nDisallow: /\n"
_ROBOTS_ALLOW = b"User-agent: *\nAllow: /\n"


class TestFetchUrl:
    @pytest.mark.asyncio
    async def test_returns_content_for_normal_page(self) -> None:
        target_url = "https://example.com/article"
        robots_url = "https://example.com/robots.txt"

        with respx.mock:
            respx.get(robots_url).mock(return_value=httpx.Response(200, content=_ROBOTS_ALLOW))
            respx.get(target_url).mock(return_value=httpx.Response(200, text=_SIMPLE_HTML))
            # Mock _check_robots to return True (robots allow)
            with patch.object(fetch_module, "_check_robots", return_value=True):
                # Mock _extract_content to return text
                with patch.object(
                    fetch_module, "_extract_content", return_value="Extracted article content."
                ):
                    content, robots_allowed = await fetch_url(target_url)

        assert robots_allowed is True
        assert content is not None
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_returns_none_false_when_robots_disallows(self) -> None:
        target_url = "https://blocked.com/secret"

        with patch.object(fetch_module, "_check_robots", return_value=False):
            content, robots_allowed = await fetch_url(target_url)

        assert content is None
        assert robots_allowed is False

    @pytest.mark.asyncio
    async def test_returns_none_when_no_extractable_content(self) -> None:
        target_url = "https://example.com/empty"

        with patch.object(fetch_module, "_check_robots", return_value=True):
            with respx.mock:
                respx.get(target_url).mock(
                    return_value=httpx.Response(200, text="<html><body></body></html>")
                )
                with patch.object(fetch_module, "_extract_content", return_value=None):
                    content, robots_allowed = await fetch_url(target_url)

        assert content is None
        assert robots_allowed is True

    @pytest.mark.asyncio
    async def test_content_wrapped_in_source_tags(self) -> None:
        target_url = "https://example.com/news"

        with patch.object(fetch_module, "_check_robots", return_value=True):
            with respx.mock:
                respx.get(target_url).mock(return_value=httpx.Response(200, text=_SIMPLE_HTML))
                with patch.object(
                    fetch_module,
                    "_extract_content",
                    return_value="Article body text.",
                ):
                    content, _ = await fetch_url(target_url)

        assert content is not None
        assert content.startswith('<source url="https://example.com/news">')
        assert content.endswith("</source>")

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self) -> None:
        target_url = "https://example.com/gone"

        with patch.object(fetch_module, "_check_robots", return_value=True):
            with respx.mock:
                respx.get(target_url).mock(return_value=httpx.Response(404))
                content, robots_allowed = await fetch_url(target_url)

        assert content is None
        assert robots_allowed is True


class TestCheckRobots:
    def test_allow_when_robots_unavailable(self) -> None:
        """If robots.txt cannot be fetched, we default to allow."""
        from research_agent.tools.fetch import _check_robots

        with patch("urllib.robotparser.RobotFileParser.read", side_effect=Exception("no robots")):
            result = _check_robots("https://example.com/page")
        assert result is True

    def test_disallow_respected(self) -> None:
        from research_agent.tools.fetch import _check_robots

        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        with patch("urllib.robotparser.RobotFileParser") as MockParser:
            MockParser.return_value = mock_rp
            result = _check_robots("https://example.com/page")
        assert result is False
