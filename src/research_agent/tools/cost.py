from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

# Pricing per 1M tokens (input/output) as of 2025
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-opus-4-5": {"input": 15.0, "output": 75.0},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
}

# Search call costs (per call)
SEARCH_PRICING: dict[str, float] = {
    "brave": 0.005,
    "exa": 0.01,
    "firecrawl": 0.005,
    "tavily": 0.008,
}


@dataclass
class CostTracker:
    """Track cumulative cost across LLM calls and search calls for a research run."""

    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_dollars: float = 0.0
    total_search_calls: int = 0
    calls_by_provider: dict[str, int] = field(default_factory=dict)
    dollars_by_provider: dict[str, float] = field(default_factory=dict)

    def record_llm_call(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Record an LLM call and return the cost in dollars.

        If the model is unknown, logs a warning and returns 0.0.
        """
        pricing = PRICING.get(model)
        if pricing is None:
            logger.warning("unknown_model_no_pricing", model=model)
            cost = 0.0
        else:
            cost = (tokens_in / 1_000_000) * pricing["input"] + (tokens_out / 1_000_000) * pricing[
                "output"
            ]

        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.total_dollars += cost

        # Track per-provider (model family) dollars
        provider_key = _model_to_provider(model)
        self.dollars_by_provider[provider_key] = (
            self.dollars_by_provider.get(provider_key, 0.0) + cost
        )

        return cost

    def record_search_call(self, provider: str) -> float:
        """Record a search API call and return the cost in dollars."""
        cost = SEARCH_PRICING.get(provider, 0.0)
        if provider not in SEARCH_PRICING:
            logger.warning("unknown_search_provider_no_pricing", provider=provider)

        self.total_search_calls += 1
        self.total_dollars += cost
        self.calls_by_provider[provider] = self.calls_by_provider.get(provider, 0) + 1
        self.dollars_by_provider[provider] = self.dollars_by_provider.get(provider, 0.0) + cost

        return cost

    def summary(self) -> dict:
        """Return a summary dict suitable for the audit log."""
        return {
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_tokens": self.total_tokens_in + self.total_tokens_out,
            "total_dollars": round(self.total_dollars, 6),
            "total_search_calls": self.total_search_calls,
            "calls_by_provider": dict(self.calls_by_provider),
            "dollars_by_provider": {k: round(v, 6) for k, v in self.dollars_by_provider.items()},
        }


def _model_to_provider(model: str) -> str:
    """Map a model string to a broad provider key for grouping."""
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gpt"):
        return "openai"
    if model.startswith("gemini"):
        return "google"
    return model
