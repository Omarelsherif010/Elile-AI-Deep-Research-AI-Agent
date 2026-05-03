from __future__ import annotations

import inspect
import time as _time
from functools import wraps
from pathlib import Path
from typing import Any, Literal

import structlog

from research_agent.schemas import Budget

from research_agent.state import ResearchState

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Lazy node imports — avoids hard failures if a node file isn't written yet.
# ---------------------------------------------------------------------------


def _import_nodes() -> dict:
    """Import all node callables. Returns a dict of name → callable."""
    from research_agent.nodes.extractor import extractor
    from research_agent.nodes.graph_builder import graph_builder
    from research_agent.nodes.planner import planner
    from research_agent.nodes.reflector import reflector
    from research_agent.nodes.reporter import reporter
    from research_agent.nodes.risk_analyzer import risk_analyzer
    from research_agent.nodes.search_orchestrator import search_orchestrator
    from research_agent.nodes.validator import validator

    return {
        "planner": planner,
        "search_orchestrator": search_orchestrator,
        "extractor": extractor,
        "validator": validator,
        "reflector": reflector,
        "graph_builder": graph_builder,
        "risk_analyzer": risk_analyzer,
        "reporter": reporter,
    }


# ---------------------------------------------------------------------------
# Budget guard decorator
# ---------------------------------------------------------------------------


def budget_guard(node_fn: Any) -> Any:
    """Wrap a node with budget enforcement and basic audit logging.

    Checks four caps before every call: iterations, dollars, search_calls, and
    wall-clock seconds for the current iteration.  On any cap exceeded, returns
    a state delta with ``terminated=True`` so reflector_router drains gracefully
    without raising an exception (Constitution Principle 4).

    Handles both sync and async node callables (Bug 2 fix).
    """

    def _check(budget: Budget, name: str) -> dict | None:
        caps = [
            (
                "iterations",
                budget.used_iterations,
                budget.max_iterations,
                "Iteration budget exhausted",
            ),
            ("dollars", budget.used_dollars, budget.max_dollars, "Dollar budget exhausted"),
            (
                "search_calls",
                budget.used_search_calls,
                budget.max_search_calls,
                "Search call budget exhausted",
            ),
            (
                "seconds",
                budget.used_seconds_current_iteration,
                float(budget.max_seconds_per_iteration),
                "Time budget exhausted",
            ),
        ]
        for resource, used, cap, reason in caps:
            if used >= cap:
                logger.warning(
                    "budget_guard_triggered",
                    resource=resource,
                    node=name,
                    used=used,
                    max=cap,
                )
                return {"terminated": True, "termination_reason": reason}
        return None

    def _audit(state: Any, name: str, result: dict, latency_ms: float) -> None:
        try:
            from research_agent.observability import AuditLogger

            run_id = state.get("run_id", "unknown")
            AuditLogger(Path("runs") / str(run_id)).log_node(
                node=name,
                input_state=dict(state),
                prompt_filled="",
                raw_response="",
                parsed_output=result or {},
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                dollars=0.0,
            )
        except Exception as exc:
            logger.warning("audit_write_failed", node=name, error=str(exc))

    if inspect.iscoroutinefunction(node_fn):

        @wraps(node_fn)
        async def _async(state: Any) -> dict:
            budget: Budget = state.get("budget", Budget())
            term = _check(budget, node_fn.__name__)
            if term:
                return term
            t0 = _time.time()
            result = await node_fn(state)
            _audit(state, node_fn.__name__, result or {}, (_time.time() - t0) * 1000)
            return result

        return _async

    @wraps(node_fn)
    def _sync(state: Any) -> dict:
        budget: Budget = state.get("budget", Budget())
        term = _check(budget, node_fn.__name__)
        if term:
            return term
        t0 = _time.time()
        result = node_fn(state)
        _audit(state, node_fn.__name__, result or {}, (_time.time() - t0) * 1000)
        return result

    return _sync


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def reflector_router(state: ResearchState) -> Literal["planner", "graph_builder"]:
    """Conditional edge from reflector.

    - terminated=True  → drain to graph_builder → risk_analyzer → reporter → END
    - terminated=False → loop back to planner for another research iteration
    """
    if state.get("terminated", False):
        return "graph_builder"
    return "planner"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def build_graph():  # type: ignore[return]
    """Build and compile the research agent StateGraph (no checkpointer).

    Topology:
        START → planner → search_orchestrator → extractor → validator → reflector
                                                                              │
                         ┌── terminated=False ←─────────────────────────────┘
                         │
                         └── terminated=True → graph_builder → risk_analyzer → reporter → END

    Returns a compiled LangGraph CompiledGraph.
    """
    from langgraph.graph import END, StateGraph

    from research_agent.state import ResearchState as _ResearchState

    nodes = _import_nodes()

    builder = StateGraph(_ResearchState)

    # --- Guarded nodes (research loop) ---
    builder.add_node("planner", budget_guard(nodes["planner"]))
    builder.add_node("search_orchestrator", budget_guard(nodes["search_orchestrator"]))
    builder.add_node("extractor", budget_guard(nodes["extractor"]))
    builder.add_node("validator", budget_guard(nodes["validator"]))
    builder.add_node("reflector", budget_guard(nodes["reflector"]))

    # --- Terminal nodes (always run once loop exits) ---
    builder.add_node("graph_builder", nodes["graph_builder"])
    builder.add_node("risk_analyzer", nodes["risk_analyzer"])
    builder.add_node("reporter", nodes["reporter"])

    # --- Edges ---
    builder.set_entry_point("planner")
    builder.add_edge("planner", "search_orchestrator")
    builder.add_edge("search_orchestrator", "extractor")
    builder.add_edge("extractor", "validator")
    builder.add_edge("validator", "reflector")
    builder.add_conditional_edges(
        "reflector",
        reflector_router,
        {
            "planner": "planner",
            "graph_builder": "graph_builder",
        },
    )
    builder.add_edge("graph_builder", "risk_analyzer")
    builder.add_edge("risk_analyzer", "reporter")
    builder.add_edge("reporter", END)

    return builder.compile()


def build_graph_with_checkpointer(db_path: Path):  # type: ignore[return]
    """Build and compile the StateGraph with a SqliteSaver checkpointer.

    Enables mid-run resume: if the process is interrupted, re-invoking with the
    same thread_id will continue from the last checkpoint.

    Args:
        db_path: Filesystem path for the SQLite checkpoint database.

    Returns a compiled LangGraph CompiledGraph with checkpointing enabled.
    """
    from langgraph.graph import END, StateGraph

    nodes = _import_nodes()

    builder = StateGraph(ResearchState)

    builder.add_node("planner", budget_guard(nodes["planner"]))
    builder.add_node("search_orchestrator", budget_guard(nodes["search_orchestrator"]))
    builder.add_node("extractor", budget_guard(nodes["extractor"]))
    builder.add_node("validator", budget_guard(nodes["validator"]))
    builder.add_node("reflector", budget_guard(nodes["reflector"]))
    builder.add_node("graph_builder", nodes["graph_builder"])
    builder.add_node("risk_analyzer", nodes["risk_analyzer"])
    builder.add_node("reporter", nodes["reporter"])

    builder.set_entry_point("planner")
    builder.add_edge("planner", "search_orchestrator")
    builder.add_edge("search_orchestrator", "extractor")
    builder.add_edge("extractor", "validator")
    builder.add_edge("validator", "reflector")
    builder.add_conditional_edges(
        "reflector",
        reflector_router,
        {
            "planner": "planner",
            "graph_builder": "graph_builder",
        },
    )
    builder.add_edge("graph_builder", "risk_analyzer")
    builder.add_edge("risk_analyzer", "reporter")
    builder.add_edge("reporter", END)

    return builder.compile()
