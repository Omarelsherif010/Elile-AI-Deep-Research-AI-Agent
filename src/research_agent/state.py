from __future__ import annotations

from typing import TypedDict

from research_agent.schemas import (
    AuditEntry,
    Budget,
    Claim,
    Entity,
    Relation,
    ResearchPlan,
    RiskFlag,
    SearchTurn,
    Source,
    TargetProfile,
    ValidatedClaim,
)


class ResearchState(TypedDict, total=False):
    run_id: str  # required
    target: TargetProfile  # required
    iteration: int
    plan: ResearchPlan | None
    search_turns: list[SearchTurn]
    claims: list[Claim]
    validated_claims: list[ValidatedClaim]
    entities: list[Entity]
    relations: list[Relation]
    sources: list[Source]
    risk_flags: list[RiskFlag]
    gaps: list[str]  # dimensions not yet explored
    budget: Budget
    audit_entries: list[AuditEntry]
    terminated: bool
    termination_reason: str


def create_initial_state(
    target: TargetProfile,
    run_id: str,
    budget: Budget | None = None,
) -> ResearchState:
    """Create initial ResearchState with all lists empty, iteration=0, terminated=False."""
    return ResearchState(
        run_id=run_id,
        target=target,
        iteration=0,
        plan=None,
        search_turns=[],
        claims=[],
        validated_claims=[],
        entities=[],
        relations=[],
        sources=[],
        risk_flags=[],
        gaps=[],
        budget=budget if budget is not None else Budget(),
        audit_entries=[],
        terminated=False,
        termination_reason="",
    )
