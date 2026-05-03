from __future__ import annotations


class ResearchAgentError(Exception):
    """Base error for all research agent errors."""


class BudgetExceeded(ResearchAgentError):
    def __init__(self, resource: str, used: float, max_: float) -> None:
        self.resource = resource
        self.used = used
        self.max_ = max_
        super().__init__(f"Budget exceeded: {resource} used {used} of {max_}")


class GuardrailViolation(ResearchAgentError):
    def __init__(self, rule: str, detail: str = "") -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"Guardrail violation [{rule}]: {detail}")


class ProviderUnavailable(ResearchAgentError):
    def __init__(self, provider: str, reason: str = "") -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"Provider unavailable: {provider}" + (f" — {reason}" if reason else ""))


class SchemaValidationError(ResearchAgentError):
    def __init__(self, model: str, detail: str = "") -> None:
        self.model = model
        self.detail = detail
        super().__init__(f"Schema validation error for {model}: {detail}")
