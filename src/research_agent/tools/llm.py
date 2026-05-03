from __future__ import annotations

import os
import string
from pathlib import Path
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from research_agent.errors import ProviderUnavailable, SchemaValidationError

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# Model IDs
CLAUDE_OPUS_4 = "claude-opus-4-5"  # Use claude-opus-4-5 as proxy for claude-opus-4
GPT_41 = "gpt-4.1"
GEMINI_FLASH = "gemini-2.5-flash"

ROLE_TO_MODEL: dict[str, str] = {
    "planner": CLAUDE_OPUS_4,
    "reflector": CLAUDE_OPUS_4,
    "risk_analyzer": CLAUDE_OPUS_4,
    "reporter": CLAUDE_OPUS_4,
    "extractor": GPT_41,
    "validator": GPT_41,
    "query_expander": GEMINI_FLASH,
    "snippet_summarizer": GEMINI_FLASH,
}


class Prompt:
    """Load and render a prompt from a markdown file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._raw = self.path.read_text(encoding="utf-8")
        self._sections = self._parse_sections(self._raw)

    @staticmethod
    def _parse_sections(text: str) -> dict[str, str]:
        """Parse ## sections from the markdown prompt."""
        sections: dict[str, str] = {}
        current: str | None = None
        lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("## "):
                if current:
                    sections[current] = "\n".join(lines).strip()
                current = line[3:].strip()
                lines = []
            elif current:
                lines.append(line)
        if current:
            sections[current] = "\n".join(lines).strip()
        return sections

    def render(self, **kwargs: Any) -> str:
        """Return the full prompt with {variables} substituted.

        Uses string.Formatter so unknown placeholders (e.g. JSON code
        examples like ``{"as_of": ...}`` or ``{key: value}``) are left
        unchanged instead of raising KeyError or ValueError.
        """
        formatter = string.Formatter()
        parts: list[str] = []
        for literal, field_name, fmt_spec, conversion in formatter.parse(self._raw):
            parts.append(literal)
            if field_name is None:
                continue
            base_key = field_name.split(".")[0].split("[")[0]
            if base_key in kwargs:
                value = kwargs[base_key]
                if conversion:
                    value = formatter.convert_field(value, conversion)
                parts.append(format(value, fmt_spec or ""))
            else:
                # Preserve the original placeholder (e.g. JSON example braces)
                placeholder = "{" + field_name
                if conversion:
                    placeholder += "!" + conversion
                if fmt_spec:
                    placeholder += ":" + fmt_spec
                parts.append(placeholder + "}")
        return "".join(parts)

    def get_section(self, name: str) -> str:
        """Return content of a named ## section, or empty string if not found."""
        return self._sections.get(name, "")


class LLMRouter:
    """Route LLM calls by role to the appropriate provider and model."""

    def __init__(self) -> None:
        self._anthropic_client = None
        self._openai_client = None
        self._google_client = None

    def _get_anthropic(self):
        if not self._anthropic_client:
            import anthropic

            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ProviderUnavailable("anthropic", "ANTHROPIC_API_KEY not set")
            self._anthropic_client = anthropic.Anthropic(api_key=key)
        return self._anthropic_client

    def _get_openai(self):
        if not self._openai_client:
            import openai

            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise ProviderUnavailable("openai", "OPENAI_API_KEY not set")
            self._openai_client = openai.OpenAI(api_key=key)
        return self._openai_client

    def _get_google(self):
        if not self._google_client:
            from google import genai

            key = os.getenv("GOOGLE_API_KEY")
            if not key:
                raise ProviderUnavailable("google", "GOOGLE_API_KEY not set")
            self._google_client = genai.Client(api_key=key)
        return self._google_client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def call(
        self,
        role: str,
        prompt: str,
        output_schema: type[T] | None = None,
        max_tokens: int = 4096,
    ) -> tuple[T | str, int, int]:
        """Call the appropriate LLM for the given role.

        Returns: (parsed_output_or_text, tokens_in, tokens_out)
        """
        model = ROLE_TO_MODEL.get(role, CLAUDE_OPUS_4)

        if model.startswith("claude"):
            return self._call_anthropic(model, prompt, output_schema, max_tokens)
        elif model.startswith("gpt"):
            return self._call_openai(model, prompt, output_schema, max_tokens)
        elif model.startswith("gemini"):
            return self._call_google(model, prompt, output_schema, max_tokens)
        else:
            raise ProviderUnavailable(model, f"Unknown model: {model}")

    def _call_anthropic(
        self,
        model: str,
        prompt: str,
        output_schema: type[T] | None,
        max_tokens: int,
    ) -> tuple[T | str, int, int]:
        client = self._get_anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens

        if output_schema:
            return self._parse_json_response(text, output_schema), tokens_in, tokens_out
        return text, tokens_in, tokens_out

    def _call_openai(
        self,
        model: str,
        prompt: str,
        output_schema: type[T] | None,
        max_tokens: int,
    ) -> tuple[T | str, int, int]:
        client = self._get_openai()
        if output_schema:
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=output_schema,
                max_tokens=max_tokens,
            )
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            return response.choices[0].message.parsed, tokens_in, tokens_out
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            return response.choices[0].message.content, tokens_in, tokens_out

    def _call_google(
        self,
        model: str,
        prompt: str,
        output_schema: type[T] | None,
        max_tokens: int,
    ) -> tuple[T | str, int, int]:
        client = self._get_google()
        response = client.models.generate_content(model=model, contents=prompt)
        text = response.text
        # google-genai SDK provides usage_metadata when available; fall back to estimate
        usage = getattr(response, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", None) or len(prompt.split()) * 4 // 3
        tokens_out = getattr(usage, "candidates_token_count", None) or len(text.split()) * 4 // 3

        if output_schema:
            return self._parse_json_response(text, output_schema), tokens_in, tokens_out
        return text, tokens_in, tokens_out

    def _parse_json_response(self, text: str, schema: type[T]) -> T:
        """Parse JSON from LLM response text into a Pydantic model."""
        import json
        import re

        # Extract JSON from markdown code blocks if present
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1)
        try:
            data = json.loads(text.strip())
            return schema.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            raise SchemaValidationError(schema.__name__, str(exc)) from exc
