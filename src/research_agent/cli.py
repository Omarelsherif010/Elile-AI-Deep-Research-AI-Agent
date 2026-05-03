from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

import structlog
from dotenv import load_dotenv

from research_agent.errors import BudgetExceeded, ProviderUnavailable
from research_agent.guardrails import Guardrails
from research_agent.schemas import Budget, TargetProfile
from research_agent.state import create_initial_state

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main CLI entry point.  Invoked by `python -m research_agent` or the
    `research-agent` console-script defined in pyproject.toml.
    """
    load_dotenv()
    _configure_logging()

    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="OSINT research agent for public figures",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ------------------------------------------------------------------
    # `run` sub-command
    # ------------------------------------------------------------------
    run_parser = subparsers.add_parser("run", help="Execute a research investigation")
    run_parser.add_argument("--target", required=True, help="Target person's full name")
    run_parser.add_argument("--aliases", default="", help="Comma-separated alternate names")
    run_parser.add_argument("--role", default=None, help="Target's role/title")
    run_parser.add_argument("--org", default=None, help="Target's organization")
    run_parser.add_argument("--context", default=None, help="Additional context")
    run_parser.add_argument("--geo", default=None, help="Geographic hint")
    run_parser.add_argument(
        "--output", default=None, help="Output directory (default: runs/<uuid>)"
    )
    run_parser.add_argument("--max-iterations", type=int, default=None, dest="max_iterations")
    run_parser.add_argument("--max-search-calls", type=int, default=None, dest="max_search_calls")
    run_parser.add_argument("--max-dollars", type=float, default=None, dest="max_dollars")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(asyncio.run(_run_investigation(args)))


# ---------------------------------------------------------------------------
# `run` implementation
# ---------------------------------------------------------------------------


async def _run_investigation(args: argparse.Namespace) -> int:
    """Execute a research investigation end-to-end.

    Returns an exit code:
        0 — success
        1 — input validation failure
        2 — budget exhausted (partial results available)
        3 — search provider failure (coverage-gap report available)
        4 — unrecoverable error
    """
    guardrails = Guardrails()

    # Validate input before doing anything else.
    try:
        guardrails.validate_input(args.target)
    except Exception as exc:
        logger.error("input_validation_failed", error=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Build target profile from CLI arguments.
    aliases = [a.strip() for a in args.aliases.split(",") if a.strip()] if args.aliases else []
    target = TargetProfile(
        name=args.target,
        aliases=aliases,
        role=args.role,
        organization=args.org,
        context=args.context,
        geographic_hint=args.geo,
    )

    # Apply budget overrides; fall back to env vars, then schema defaults.
    budget = Budget(
        max_iterations=args.max_iterations or int(os.getenv("DEFAULT_MAX_ITERATIONS", "8")),
        max_search_calls=args.max_search_calls or int(os.getenv("DEFAULT_MAX_SEARCH_CALLS", "60")),
        max_dollars=args.max_dollars or float(os.getenv("DEFAULT_MAX_DOLLARS", "5.0")),
    )

    # Determine output directory.
    run_id = str(uuid.uuid4())[:8]
    output_dir = Path(args.output) if args.output else Path("runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build initial LangGraph state.
    state = create_initial_state(
        target=target,
        run_id=str(output_dir.name),
        budget=budget,
    )

    try:
        from research_agent.graph import build_graph_with_checkpointer

        checkpoint_path = output_dir / "checkpoint.sqlite"
        graph = build_graph_with_checkpointer(checkpoint_path)
        config = {"configurable": {"thread_id": run_id}}

        print(f"Starting research on: {target.name}")
        print(f"Output:               {output_dir}")

        await graph.ainvoke(state, config=config)  # type: ignore[var-annotated]

        # Warn if expected report artefacts are absent.
        expected_outputs = ["report.md", "report.json", "graph_export.json"]
        missing = [o for o in expected_outputs if not (output_dir / o).exists()]
        if missing:
            print(
                f"Warning: some outputs missing: {missing}",
                file=sys.stderr,
            )

        print(f"\nComplete. Reports in: {output_dir}")
        return 0

    except BudgetExceeded as exc:
        logger.warning("budget_exhausted", error=str(exc))
        print(f"Budget exhausted. Partial results in: {output_dir}", file=sys.stderr)
        return 2

    except ProviderUnavailable as exc:
        logger.error("provider_failed", error=str(exc))
        print(
            f"Search provider failed. Coverage-gap report in: {output_dir}",
            file=sys.stderr,
        )
        return 3

    except Exception as exc:
        logger.error("unrecoverable_error", error=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 4


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    """Configure structlog for human-readable console output."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
