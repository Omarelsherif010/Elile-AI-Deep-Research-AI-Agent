from __future__ import annotations

from research_agent.schemas import RiskCategory, RiskSeverity

# Re-export for consumers of this module
__all__ = ["RiskCategory", "RiskSeverity", "SEVERITY_ORDER", "COVERAGE_GAP_DIMENSIONS"]

# Mapping from RiskSeverity to an integer for sorting purposes.
# Higher integer = higher severity.
SEVERITY_ORDER: dict[RiskSeverity, int] = {
    RiskSeverity.LOW: 1,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.HIGH: 3,
    RiskSeverity.CRITICAL: 4,
}

# The 6 research dimensions that can have coverage gaps.
COVERAGE_GAP_DIMENSIONS: set[str] = {
    "biographical",
    "professional",
    "financial",
    "network",
    "statements",
    "risk",
}
