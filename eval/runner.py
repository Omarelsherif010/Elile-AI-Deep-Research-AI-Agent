"""Eval runner: load personas, execute pipeline, compute metrics, emit report."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import yaml

from eval.metrics import EvalMetrics, compute_metrics

logger = structlog.get_logger()

PERSONAS_DIR = Path(__file__).parent / "personas"


class EvalRunner:
    def __init__(
        self,
        persona: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.persona_filter = persona
        self.output_dir = output_dir or Path("eval/results") / datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> list[EvalMetrics]:
        """Run eval for all (or filtered) personas."""
        persona_files = sorted(PERSONAS_DIR.glob("*.yaml"))
        if self.persona_filter:
            persona_files = [p for p in persona_files if p.stem == self.persona_filter]

        if not persona_files:
            logger.warning("no_personas_found", filter=self.persona_filter)
            return []

        all_metrics: list[EvalMetrics] = []
        for persona_file in persona_files:
            persona: dict[str, Any] = yaml.safe_load(persona_file.read_text())
            logger.info("eval_persona_start", persona=persona["name"])

            try:
                metrics = await self._run_persona(persona)
                all_metrics.append(metrics)
                self._save_persona_result(persona, metrics)
            except Exception as exc:
                logger.error("eval_persona_failed", persona=persona["name"], error=str(exc))

        self._emit_summary(all_metrics)
        return all_metrics

    async def _run_persona(self, persona: dict[str, Any]) -> EvalMetrics:
        """Execute the pipeline for one persona and compute metrics."""
        from research_agent.graph import build_graph
        from research_agent.schemas import Budget, TargetProfile
        from research_agent.state import create_initial_state

        target_data: dict[str, Any] = persona["target"]
        target = TargetProfile(
            name=target_data["name"],
            role=target_data.get("role"),
            organization=target_data.get("organization"),
            context=target_data.get("context"),
            aliases=target_data.get("aliases", []),
        )

        budget = Budget(
            max_iterations=3,  # reduced for eval speed
            max_search_calls=20,
            max_dollars=1.0,
        )

        run_id = f"eval_{persona['name']}_{datetime.now().strftime('%H%M%S')}"
        state = create_initial_state(target=target, run_id=run_id, budget=budget)

        graph = build_graph()
        config: dict[str, Any] = {"configurable": {"thread_id": run_id}}

        run_dir = Path("runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        await graph.ainvoke(state, config=config)

        report_path = run_dir / "report.json"
        if report_path.exists():
            report_json: dict[str, Any] = json.loads(report_path.read_text())
        else:
            report_json = {"claims": [], "risk_flags": []}

        return compute_metrics(persona, report_json)

    def _save_persona_result(self, persona: dict[str, Any], metrics: EvalMetrics) -> None:
        thresholds: dict[str, float] = persona.get("thresholds", {})
        result: dict[str, Any] = {
            "persona": persona["name"],
            "metrics": {
                "recall_easy": metrics.recall_easy,
                "recall_medium": metrics.recall_medium,
                "recall_hard": metrics.recall_hard,
                "precision": metrics.precision,
                "confidence_calibration": metrics.confidence_calibration,
                "risk_recall": metrics.risk_recall,
            },
            "pass_fail": metrics.pass_fail(thresholds),
            "overall_pass": metrics.overall_pass(thresholds),
        }
        out_file = self.output_dir / f"{persona['name']}_result.json"
        out_file.write_text(json.dumps(result, indent=2))
        logger.info("eval_persona_done", persona=persona["name"], pass_=result["overall_pass"])

    def _emit_summary(self, all_metrics: list[EvalMetrics]) -> None:
        summary: dict[str, Any] = {
            "run_at": datetime.now().isoformat(),
            "personas_run": len(all_metrics),
            "results": [
                {
                    "persona": m.persona_name,
                    "recall_easy": m.recall_easy,
                    "recall_medium": m.recall_medium,
                    "precision": m.precision,
                    "risk_recall": m.risk_recall,
                }
                for m in all_metrics
            ],
        }
        (self.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # Print table to stdout
        print("\n=== Eval Results ===")
        print(
            f"{'Persona':<30} {'Recall/E':<10} {'Recall/M':<10} "
            f"{'Precision':<10} {'RiskRecall':<12}"
        )
        print("-" * 72)
        for m in all_metrics:
            print(
                f"{m.persona_name:<30} {m.recall_easy:<10.2f} {m.recall_medium:<10.2f} "
                f"{m.precision:<10.2f} {m.risk_recall:<12.2f}"
            )
