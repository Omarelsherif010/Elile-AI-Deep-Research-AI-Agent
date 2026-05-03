"""Markdown report rendering for the eval suite.

Uses Jinja2 templates in eval/templates/ to separate content from layout.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from eval.schemas import MetricsReport, PersonaMetrics

logger = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(),
)


def render_persona_report(metrics: PersonaMetrics) -> str:
    """Render a per-persona Markdown report from metrics."""
    template = _jinja_env.get_template("persona_report.md.j2")

    return template.render(
        persona_id=metrics.persona_id,
        run_id="",
        timestamp=datetime.now(UTC).isoformat(),
        overall_pass=all(metrics.success_criteria.values()),
        precision=metrics.precision,
        precision_is_automated=metrics.precision_is_automated,
        precision_sample_size=metrics.precision_sample_size,
        risk_recall=metrics.risk_recall,
        recall_by_tier=metrics.recall_by_tier,
        found_counts=metrics.found_by_tier,
        total_counts=metrics.total_by_tier,
        calibration_buckets=metrics.calibration_buckets,
        expected_calibration_error=metrics.expected_calibration_error,
        risk_matches=metrics.risk_matches,
        fact_matches=metrics.fact_matches,
        cost_dollars=metrics.cost_dollars,
        duration_seconds=metrics.duration_seconds,
        iterations_used=metrics.iterations_used,
        search_calls_used=metrics.search_calls_used,
        success_criteria=metrics.success_criteria,
    )


def render_combined_report(report: MetricsReport) -> str:
    """Render the combined summary Markdown report."""
    template = _jinja_env.get_template("combined_report.md.j2")
    return template.render(
        run_id=report.run_id,
        timestamp=report.timestamp.isoformat(),
        overall_pass=report.overall_pass,
        per_persona=report.per_persona,
        total_cost_dollars=report.total_cost_dollars,
        total_duration_seconds=report.total_duration_seconds,
    )


def write_report(
    report: MetricsReport,
    output_dir: Path,
    precision_samples: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    """Write all report artifacts to disk.

    Outputs:
    - {persona_id}.md per persona
    - summary.md combined report
    - metrics.json machine-readable report
    - precision_sample.json sampled claims for manual review
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for persona_metrics in report.per_persona:
        md = render_persona_report(persona_metrics)
        (output_dir / f"{persona_metrics.persona_id}.md").write_text(
            md, encoding="utf-8"
        )

    summary_md = render_combined_report(report)
    (output_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    (output_dir / "metrics.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )

    if precision_samples:
        (output_dir / "precision_sample.json").write_text(
            json.dumps(precision_samples, indent=2, default=str),
            encoding="utf-8",
        )

    logger.info(
        "reports_written",
        output_dir=str(output_dir),
        persona_count=len(report.per_persona),
    )
