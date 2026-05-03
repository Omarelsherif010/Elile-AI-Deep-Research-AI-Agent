"""CLI entry point for the eval suite.

Commands:
    run             Execute eval against one or all personas
    replay          Recompute metrics from cached artifacts
    list-personas   List available personas
    validate-persona Validate persona YAML against schema
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
import yaml
from dotenv import load_dotenv

from eval.matcher import OpenAIEmbedder, match_facts, match_risks
from eval.metrics import (
    compute_calibration,
    compute_precision,
    compute_recall,
    compute_risk_recall,
    evaluate_success_criteria,
)
from eval.reporter import write_report
from eval.runner import DEFAULT_CACHE_DIR, replay_persona, run_persona
from eval.schemas import (
    FactMatch,
    MatchStrategy,
    MetricsReport,
    PersonaDefinition,
    PersonaMetrics,
    RiskMatch,
)

logger = structlog.get_logger()

PERSONAS_DIR = Path(__file__).parent / "personas"
EVAL_BUDGET_CAP = 15.0


def _load_personas(persona_filter: str | None = None) -> list[PersonaDefinition]:
    """Load all persona YAML files, optionally filtered."""
    personas: list[PersonaDefinition] = []
    for yaml_path in sorted(PERSONAS_DIR.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        if persona_filter and yaml_path.stem != persona_filter:
            continue
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        personas.append(PersonaDefinition(**data))
    return personas


def _budget_check(personas: list[PersonaDefinition]) -> bool:
    """Check if total estimated cost exceeds cap. Prompt if so.

    Returns True if user wants to proceed, False otherwise.
    """
    total = sum(p.max_dollars for p in personas)
    if total > EVAL_BUDGET_CAP:
        print(
            f"Warning: estimated cost ${total:.2f} exceeds cap ${EVAL_BUDGET_CAP:.2f}.",
            file=sys.stderr,
        )
        response = input("Proceed anyway? (yes/no): ")
        return response.strip().lower() in ("yes", "y")
    return True


def _save_match_cache(
    path: Path,
    fact_matches: list[FactMatch],
    risk_matches: list[RiskMatch],
    embedder: OpenAIEmbedder | None,
) -> None:
    """Persist match results and embedding vectors to JSON."""
    cache: dict[str, Any] = {
        "fact_matches": [m.model_dump(mode="json") for m in fact_matches],
        "risk_matches": [m.model_dump(mode="json") for m in risk_matches],
    }
    if embedder is not None:
        cache["embeddings"] = {
            text: vec for text, vec in embedder.get_cache().items()
        }
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _load_match_cache(path: Path) -> tuple[list[FactMatch], list[RiskMatch], dict[str, list[float]]]:
    """Load match results and embedding vectors from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    fact_matches = [FactMatch(**m) for m in data.get("fact_matches", [])]
    risk_matches = [RiskMatch(**m) for m in data.get("risk_matches", [])]
    embeddings: dict[str, list[float]] = data.get("embeddings", {})
    return fact_matches, risk_matches, embeddings


def _build_persona_metrics(
    persona: PersonaDefinition,
    artifacts: Any,
    fact_matches: list[FactMatch],
    risk_matches: list[RiskMatch],
    precision_result: dict[str, Any],
    buckets: list[Any],
    ece: float,
) -> PersonaMetrics:
    """Assemble PersonaMetrics from computed pieces."""
    from eval.schemas import Tier

    recall_by_tier = compute_recall(fact_matches, persona.planted_facts)
    risk_recall_val = compute_risk_recall(risk_matches, persona.planted_risks)

    fact_tiers = {f.id: f.difficulty for f in persona.planted_facts}
    total_by_tier: dict[Tier, int] = {Tier.easy: 0, Tier.medium: 0, Tier.hard: 0}
    found_by_tier: dict[Tier, int] = {Tier.easy: 0, Tier.medium: 0, Tier.hard: 0}
    for match in fact_matches:
        tier = fact_tiers.get(match.planted_fact_id)
        if tier is None:
            continue
        total_by_tier[tier] += 1
        if match.matched_claim_id is not None:
            found_by_tier[tier] += 1

    metrics = PersonaMetrics(
        persona_id=persona.id,
        recall_by_tier=recall_by_tier,
        found_by_tier=found_by_tier,
        total_by_tier=total_by_tier,
        precision=precision_result["rate"] or 0.0,
        precision_sample_size=len(precision_result["sampled_claims"]),
        precision_is_automated=precision_result["is_automated"],
        risk_recall=risk_recall_val,
        fact_matches=fact_matches,
        risk_matches=risk_matches,
        calibration_buckets=buckets,
        expected_calibration_error=ece,
        cost_dollars=artifacts.cost_dollars,
        duration_seconds=artifacts.duration_seconds,
        iterations_used=artifacts.iterations_used,
        search_calls_used=artifacts.search_calls_used,
        success_criteria={},
    )
    metrics.success_criteria = evaluate_success_criteria(metrics)
    return metrics


def cmd_run(args: argparse.Namespace) -> int:
    """Execute eval run."""
    personas = _load_personas(args.persona)
    if not personas:
        available = [p.stem for p in PERSONAS_DIR.glob("*.yaml") if not p.name.startswith("_")]
        print(f"No personas found matching filter: {args.persona}", file=sys.stderr)
        print(f"Available personas: {', '.join(available)}", file=sys.stderr)
        return 1

    if not _budget_check(personas):
        print("Aborted.", file=sys.stderr)
        return 1

    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    cache_dir = Path(args.cache_dir)
    reports_dir = Path("eval/reports") / run_id

    embedder: OpenAIEmbedder | None = None
    if any(
        f.match_strategy == MatchStrategy.semantic
        for p in personas
        for f in p.planted_facts
    ):
        embedder = OpenAIEmbedder()

    per_persona_metrics: list[PersonaMetrics] = []
    precision_samples: dict[str, list[dict[str, Any]]] = {}
    total_cost = 0.0
    total_duration = 0.0

    for persona in personas:
        print(f"\n=== Running persona: {persona.target_name} ===")
        artifacts = run_persona(
            persona=persona,
            run_id=run_id,
            cache_dir=cache_dir,
        )
        total_cost += artifacts.cost_dollars
        total_duration += artifacts.duration_seconds

        # Load agent output
        report_data = json.loads(artifacts.report_json.read_text(encoding="utf-8"))
        claims_data = report_data.get("claims", [])
        flags_data = report_data.get("risk_flags", [])

        # Rehydrate Pydantic models
        from research_agent.schemas import RiskFlag, ValidatedClaim
        claims = [ValidatedClaim(**c) for c in claims_data]
        flags = [RiskFlag(**f) for f in flags_data]

        # Match
        fact_matches = match_facts(persona, claims, embedder)
        risk_matches = match_risks(persona, flags)

        # Persist match cache
        match_cache_path = cache_dir / run_id / persona.id / "match_cache.json"
        _save_match_cache(match_cache_path, fact_matches, risk_matches, embedder)
        artifacts.match_cache = match_cache_path

        # Metrics
        precision_result = compute_precision(
            claims, persona.planted_facts, persona.persona_type
        )
        precision_samples[persona.id] = precision_result["sampled_claims"]
        buckets, ece = compute_calibration(claims, fact_matches)

        metrics = _build_persona_metrics(
            persona, artifacts, fact_matches, risk_matches, precision_result, buckets, ece
        )
        per_persona_metrics.append(metrics)

        print(f"Recall easy: {metrics.recall_by_tier['easy']:.2f}")
        print(f"Precision:   {metrics.precision:.2f}")
        print(f"Risk recall: {metrics.risk_recall:.2f}")

    # Build combined report
    overall_pass = all(
        all(m.success_criteria.values()) for m in per_persona_metrics
    )
    report = MetricsReport(
        run_id=run_id,
        timestamp=datetime.now(UTC),
        per_persona=per_persona_metrics,
        overall_pass=overall_pass,
        total_cost_dollars=total_cost,
        total_duration_seconds=total_duration,
    )
    write_report(report, reports_dir, precision_samples)

    print("\n=== Eval complete ===")
    print(f"Reports: {reports_dir}")
    print(f"Overall: {'PASS' if overall_pass else 'FAIL'}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """Recompute metrics from cached artifacts."""
    cache_dir = Path(args.cache_dir)
    run_dir = cache_dir / args.run_id
    if not run_dir.exists():
        print(f"Run ID not found: {args.run_id}", file=sys.stderr)
        return 1

    personas = _load_personas(args.persona)
    if not personas:
        print(f"No personas found matching filter: {args.persona}", file=sys.stderr)
        return 1

    replay_id = f"{args.run_id}-replay-{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    reports_dir = Path("eval/reports") / replay_id

    per_persona_metrics: list[PersonaMetrics] = []
    precision_samples: dict[str, list[dict[str, Any]]] = {}
    total_cost = 0.0

    for persona in personas:
        persona_cache = run_dir / persona.id
        if not persona_cache.exists():
            print(f"Warning: no cache for {persona.id}, skipping.", file=sys.stderr)
            continue

        artifacts = replay_persona(persona, persona_cache)
        total_cost += artifacts.cost_dollars

        # Load cached matches — replay MUST NOT make API calls (FR-015)
        match_cache_path = persona_cache / "match_cache.json"
        if match_cache_path.exists():
            fact_matches, risk_matches, _ = _load_match_cache(match_cache_path)
        else:
            logger.warning(
                "match_cache_missing",
                persona=persona.id,
                msg="Re-matching from report data; semantic matches will use fuzzy fallback",
            )
            report_data = json.loads(artifacts.report_json.read_text(encoding="utf-8"))
            from research_agent.schemas import RiskFlag, ValidatedClaim

            claims = [ValidatedClaim(**c) for c in report_data.get("claims", [])]
            flags = [RiskFlag(**f) for f in report_data.get("risk_flags", [])]
            fact_matches = match_facts(persona, claims, embedder=None)
            risk_matches = match_risks(persona, flags)

        # Recompute metrics
        report_data = json.loads(artifacts.report_json.read_text(encoding="utf-8"))
        from research_agent.schemas import ValidatedClaim
        claims = [ValidatedClaim(**c) for c in report_data.get("claims", [])]
        precision_result = compute_precision(
            claims, persona.planted_facts, persona.persona_type
        )
        precision_samples[persona.id] = precision_result["sampled_claims"]
        buckets, ece = compute_calibration(claims, fact_matches)

        metrics = _build_persona_metrics(
            persona, artifacts, fact_matches, risk_matches, precision_result, buckets, ece
        )
        per_persona_metrics.append(metrics)

    overall_pass = all(
        all(m.success_criteria.values()) for m in per_persona_metrics
    )
    report = MetricsReport(
        run_id=replay_id,
        timestamp=datetime.now(UTC),
        per_persona=per_persona_metrics,
        overall_pass=overall_pass,
        total_cost_dollars=total_cost,
        total_duration_seconds=0.0,
    )
    write_report(report, reports_dir, precision_samples)

    print(f"Replay complete: {reports_dir}")
    return 0


def cmd_list_personas(_args: argparse.Namespace) -> int:
    """List available personas."""
    personas = _load_personas()
    print(f"{'ID':<25} {'Type':<15} {'Name':<25} {'Facts':>6} {'Risks':>6}")
    print("-" * 80)
    for p in personas:
        print(
            f"{p.id:<25} {p.persona_type.value:<15} {p.target_name:<25} "
            f"{len(p.planted_facts):>6} {len(p.planted_risks):>6}"
        )
    return 0


def cmd_validate_persona(args: argparse.Namespace) -> int:
    """Validate persona YAML against schema."""
    if args.all:
        personas = _load_personas()
    elif args.persona:
        personas = _load_personas(args.persona)
        if not personas:
            available = [p.stem for p in PERSONAS_DIR.glob("*.yaml") if not p.name.startswith("_")]
            print(f"Invalid persona ID: {args.persona}", file=sys.stderr)
            print(f"Available: {', '.join(available)}", file=sys.stderr)
            return 1
    else:
        print("Provide --persona ID or --all", file=sys.stderr)
        return 1

    all_valid = True
    for p in personas:
        try:
            # Synthetic personas must have plant_site_root
            if p.persona_type.value == "synthetic" and not p.plant_site_root:
                print(f"FAIL {p.id}: synthetic persona missing plant_site_root")
                all_valid = False
                continue
            print(f"OK   {p.id} ({len(p.planted_facts)} facts, {len(p.planted_risks)} risks)")
        except Exception as exc:
            print(f"FAIL {p.id}: {exc}")
            all_valid = False

    return 0 if all_valid else 1


def main() -> int:
    """Main CLI entry point."""
    load_dotenv()
    parser = argparse.ArgumentParser(prog="eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = subparsers.add_parser("run", help="Run eval suite")
    run_parser.add_argument("--persona", default=None, help="Run single persona")
    run_parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Cache directory")

    # replay
    replay_parser = subparsers.add_parser("replay", help="Replay from cache")
    replay_parser.add_argument("--run-id", required=True, help="Previous run ID")
    replay_parser.add_argument("--persona", default=None, help="Replay single persona")
    replay_parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Cache directory")

    # list-personas
    subparsers.add_parser("list-personas", help="List available personas")

    # validate-persona
    validate_parser = subparsers.add_parser("validate-persona", help="Validate persona YAML")
    validate_parser.add_argument("--persona", default=None, help="Persona ID")
    validate_parser.add_argument("--all", action="store_true", help="Validate all personas")

    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "replay":
        return cmd_replay(args)
    elif args.command == "list-personas":
        return cmd_list_personas(args)
    elif args.command == "validate-persona":
        return cmd_validate_persona(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
