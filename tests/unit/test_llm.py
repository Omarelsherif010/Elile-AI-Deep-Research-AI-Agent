from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from research_agent.errors import ProviderUnavailable, SchemaValidationError
from research_agent.tools.llm import (
    CLAUDE_OPUS_4,
    GEMINI_FLASH,
    GPT_41,
    ROLE_TO_MODEL,
    LLMRouter,
    Prompt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SampleSchema(BaseModel):
    name: str
    value: int


def _write_prompt_file(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test_prompt.md"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


class TestPromptRender:
    def test_simple_substitution(self, tmp_path: Path) -> None:
        path = _write_prompt_file(tmp_path, "Hello {name}! You are a {role}.")
        prompt = Prompt(path)
        rendered = prompt.render(name="Jane", role="researcher")
        assert rendered == "Hello Jane! You are a researcher."

    def test_no_variables_unchanged(self, tmp_path: Path) -> None:
        raw = "No variables here."
        path = _write_prompt_file(tmp_path, raw)
        prompt = Prompt(path)
        assert prompt.render() == raw

    def test_multiple_substitutions(self, tmp_path: Path) -> None:
        path = _write_prompt_file(tmp_path, "{a} {b} {a}")
        prompt = Prompt(path)
        assert prompt.render(a="X", b="Y") == "X Y X"


class TestPromptParseSections:
    def test_single_section(self, tmp_path: Path) -> None:
        path = _write_prompt_file(tmp_path, "## Role\nYou are an agent.\n")
        prompt = Prompt(path)
        assert prompt.get_section("Role") == "You are an agent."

    def test_multiple_sections(self, tmp_path: Path) -> None:
        content = "## Role\nAgent role.\n\n## Task\nDo the task.\n"
        path = _write_prompt_file(tmp_path, content)
        prompt = Prompt(path)
        assert prompt.get_section("Role") == "Agent role."
        assert prompt.get_section("Task") == "Do the task."

    def test_missing_section_returns_empty(self, tmp_path: Path) -> None:
        path = _write_prompt_file(tmp_path, "## Role\nAgent role.\n")
        prompt = Prompt(path)
        assert prompt.get_section("Nonexistent") == ""

    def test_no_sections_returns_empty_dict(self, tmp_path: Path) -> None:
        path = _write_prompt_file(tmp_path, "Just plain text.\n")
        prompt = Prompt(path)
        assert prompt.get_section("Anything") == ""


# ---------------------------------------------------------------------------
# LLMRouter — model routing
# ---------------------------------------------------------------------------


class TestLLMRouterModelRouting:
    def test_planner_uses_claude(self) -> None:
        assert ROLE_TO_MODEL["planner"] == CLAUDE_OPUS_4

    def test_reflector_uses_claude(self) -> None:
        assert ROLE_TO_MODEL["reflector"] == CLAUDE_OPUS_4

    def test_extractor_uses_gpt(self) -> None:
        assert ROLE_TO_MODEL["extractor"] == GPT_41

    def test_validator_uses_gpt(self) -> None:
        assert ROLE_TO_MODEL["validator"] == GPT_41

    def test_query_expander_uses_gemini(self) -> None:
        assert ROLE_TO_MODEL["query_expander"] == GEMINI_FLASH

    def test_snippet_summarizer_uses_gemini(self) -> None:
        assert ROLE_TO_MODEL["snippet_summarizer"] == GEMINI_FLASH

    def test_unknown_role_falls_back_to_claude(self) -> None:
        router = LLMRouter()
        # Verify that call() dispatches to _call_anthropic for unknown role
        with patch.object(router, "_call_anthropic", return_value=("text", 10, 5)) as mock_call:
            router.call("unknown_role", "prompt")
            mock_call.assert_called_once()

    def test_planner_role_calls_anthropic(self) -> None:
        router = LLMRouter()
        with patch.object(router, "_call_anthropic", return_value=("text", 10, 5)) as mock_call:
            result = router.call("planner", "test prompt")
            mock_call.assert_called_once()
            assert result == ("text", 10, 5)

    def test_extractor_role_calls_openai(self) -> None:
        router = LLMRouter()
        with patch.object(router, "_call_openai", return_value=("text", 10, 5)) as mock_call:
            router.call("extractor", "test prompt")
            mock_call.assert_called_once()

    def test_query_expander_role_calls_google(self) -> None:
        router = LLMRouter()
        with patch.object(router, "_call_google", return_value=("text", 10, 5)) as mock_call:
            router.call("query_expander", "test prompt")
            mock_call.assert_called_once()


# ---------------------------------------------------------------------------
# LLMRouter — provider unavailable when key missing
# ---------------------------------------------------------------------------


class TestProviderUnavailable:
    def test_anthropic_raises_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        router = LLMRouter()
        with pytest.raises(ProviderUnavailable, match="anthropic"):
            router._get_anthropic()

    def test_openai_raises_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        router = LLMRouter()
        with pytest.raises(ProviderUnavailable, match="openai"):
            router._get_openai()

    def test_google_raises_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        router = LLMRouter()
        with pytest.raises(ProviderUnavailable, match="google"):
            router._get_google()


# ---------------------------------------------------------------------------
# LLMRouter — JSON parsing
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def test_plain_json(self) -> None:
        router = LLMRouter()
        result = router._parse_json_response('{"name": "Jane", "value": 42}', _SampleSchema)
        assert result.name == "Jane"
        assert result.value == 42

    def test_json_in_code_block(self) -> None:
        router = LLMRouter()
        text = '```json\n{"name": "Bob", "value": 7}\n```'
        result = router._parse_json_response(text, _SampleSchema)
        assert result.name == "Bob"
        assert result.value == 7

    def test_json_in_plain_code_block(self) -> None:
        router = LLMRouter()
        text = '```\n{"name": "Alice", "value": 1}\n```'
        result = router._parse_json_response(text, _SampleSchema)
        assert result.name == "Alice"

    def test_invalid_json_raises_schema_validation_error(self) -> None:
        router = LLMRouter()
        with pytest.raises(SchemaValidationError):
            router._parse_json_response("not json at all", _SampleSchema)

    def test_valid_json_wrong_schema_raises(self) -> None:
        router = LLMRouter()
        with pytest.raises(SchemaValidationError):
            # missing required "value" field
            router._parse_json_response('{"name": "Jane"}', _SampleSchema)
