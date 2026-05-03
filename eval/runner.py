"""Eval runner: invoke the agent CLI as a subprocess and collect artifacts.

Provides two entry points:
- run_persona(): live agent invocation
- replay_persona(): reconstruct RunArtifacts from cached files
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import structlog

from eval.schemas import PersonaDefinition, RunArtifacts

logger = structlog.get_logger()

DEFAULT_CACHE_DIR = Path("eval/cache")


def run_persona(
    persona: PersonaDefinition,
    run_id: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    env_overrides: dict[str, str] | None = None,
) -> RunArtifacts:
    """Invoke the agent CLI for one persona and collect artifacts.

    Args:
        persona: The persona definition to run against.
        run_id: Unique identifier for this eval run.
        cache_dir: Where to cache artifacts.
        env_overrides: Optional environment variable overrides.

    Returns:
        RunArtifacts populated with paths and metadata.
    """
    agent_run_dir = Path("runs") / f"eval_{run_id}_{persona.id}"
    agent_run_dir.mkdir(parents=True, exist_ok=True)

    persona_cache_dir = cache_dir / run_id / persona.id
    persona_cache_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "research_agent",
        "run",
        "--target",
        persona.target_name,
        "--context",
        persona.target_context,
        "--output",
        str(agent_run_dir),
        "--max-iterations",
        str(persona.max_iterations or 3),
        "--max-dollars",
        str(persona.max_dollars or 5.0),
    ]

    env = {**dict(os.environ), **(env_overrides or {})}

    stdout_log = persona_cache_dir / "agent_stdout.log"
    stderr_log = persona_cache_dir / "agent_stderr.log"

    logger.info("eval_subprocess_start", persona=persona.id, run_id=run_id)
    t0 = time.time()

    with stdout_log.open("w", encoding="utf-8") as stdout_fh, stderr_log.open(
        "w", encoding="utf-8"
    ) as stderr_fh:
        result = subprocess.run(
            cmd,
            stdout=stdout_fh,
            stderr=stderr_fh,
            env=env,
            check=False,
        )

    duration = time.time() - t0
    exit_code = result.returncode

    logger.info(
        "eval_subprocess_complete",
        persona=persona.id,
        run_id=run_id,
        exit_code=exit_code,
        duration=duration,
    )

    # Copy artifacts to cache
    report_src = agent_run_dir / "report.json"
    audit_src = agent_run_dir / "audit.json"
    report_dst = persona_cache_dir / "report.json"
    audit_dst = persona_cache_dir / "audit.json"

    if report_src.exists():
        shutil.copy2(report_src, report_dst)
    else:
        report_dst.write_text("{}", encoding="utf-8")
        logger.warning("report_json_missing", persona=persona.id, run_id=run_id)

    if audit_src.exists():
        shutil.copy2(audit_src, audit_dst)
    else:
        audit_dst.write_text("{}", encoding="utf-8")
        logger.warning("audit_json_missing", persona=persona.id, run_id=run_id)

    # Parse metadata from audit.json and report.json
    cost_dollars, iterations_used, search_calls_used = _parse_audit(audit_dst)
    if cost_dollars == 0.0:
        # Fallback to budget_used in report.json
        cost_dollars, iterations_used, search_calls_used = _parse_report_budget(report_dst)

    artifacts = RunArtifacts(
        persona_id=persona.id,
        run_id=run_id,
        agent_run_dir=agent_run_dir,
        report_json=report_dst,
        audit_json=audit_dst,
        cost_dollars=cost_dollars,
        duration_seconds=duration,
        iterations_used=iterations_used,
        search_calls_used=search_calls_used,
        exit_code=exit_code,
    )

    return artifacts


def replay_persona(
    persona: PersonaDefinition,
    run_dir: Path,
) -> RunArtifacts:
    """Reconstruct RunArtifacts from cached files without invoking the agent.

    Args:
        persona: The persona definition.
        run_dir: The cached run directory (e.g., eval/cache/{run_id}/{persona_id}).

    Returns:
        RunArtifacts populated from cached files.
    """
    report_json = run_dir / "report.json"
    audit_json = run_dir / "audit.json"

    if not report_json.exists():
        raise FileNotFoundError(f"report.json not found in {run_dir}")
    if not audit_json.exists():
        raise FileNotFoundError(f"audit.json not found in {run_dir}")

    cost_dollars, iterations_used, search_calls_used = _parse_audit(audit_json)
    if cost_dollars == 0.0:
        cost_dollars, iterations_used, search_calls_used = _parse_report_budget(report_json)

    return RunArtifacts(
        persona_id=persona.id,
        run_id=run_dir.parent.name,
        agent_run_dir=run_dir,
        report_json=report_json,
        audit_json=audit_json,
        match_cache=run_dir / "match_cache.json" if (run_dir / "match_cache.json").exists() else None,
        cost_dollars=cost_dollars,
        duration_seconds=0.0,  # unknown for replay
        iterations_used=iterations_used,
        search_calls_used=search_calls_used,
        exit_code=0,
    )


def _parse_audit(audit_path: Path) -> tuple[float, int, int]:
    """Parse audit.json (JSONL) for cost summary.

    Returns (cost_dollars, iterations_used, search_calls_used).
    """
    cost_dollars = 0.0
    iterations_used = 0
    search_calls_used = 0

    if not audit_path.exists():
        return cost_dollars, iterations_used, search_calls_used

    try:
        with audit_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("type") == "cost_summary":
                    cost_dollars = entry.get("total_dollars", 0.0)
                    iterations_used = entry.get("iterations", 0)
                    search_calls_used = entry.get("total_search_calls", 0)
                    return cost_dollars, iterations_used, search_calls_used
                # Accumulate dollars from individual entries as fallback
                cost_dollars += entry.get("dollars", 0.0)
    except (json.JSONDecodeError, OSError):
        logger.warning("audit_parse_failed", path=str(audit_path))

    return cost_dollars, iterations_used, search_calls_used


def _parse_report_budget(report_path: Path) -> tuple[float, int, int]:
    """Parse report.json for budget_used as fallback.

    Returns (cost_dollars, iterations_used, search_calls_used).
    """
    cost_dollars = 0.0
    iterations_used = 0
    search_calls_used = 0

    if not report_path.exists():
        return cost_dollars, iterations_used, search_calls_used

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        budget = data.get("budget_used", {})
        cost_dollars = budget.get("used_dollars", 0.0)
        iterations_used = budget.get("used_iterations", 0)
        search_calls_used = budget.get("used_search_calls", 0)
    except (json.JSONDecodeError, OSError):
        logger.warning("report_parse_failed", path=str(report_path))

    return cost_dollars, iterations_used, search_calls_used
