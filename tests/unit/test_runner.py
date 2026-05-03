"""Unit tests for eval/runner.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from eval.runner import replay_persona, run_persona
from eval.schemas import PersonaDefinition, PersonaType, PlantedFact, ResearchDimension, Tier


def _make_persona() -> PersonaDefinition:
    return PersonaDefinition(
        id="persona_test",
        target_name="Test Person",
        target_context="Test context",
        persona_type=PersonaType.synthetic,
        description="Test",
        ethical_notes="Test",
        plant_site_root="eval/plant_site/test",
        planted_facts=[
            PlantedFact(
                id="fact_t01",
                statement="Test fact",
                difficulty=Tier.easy,
                expected_dimension=ResearchDimension.biographical,
                fact_type="biographical",
                notes="test",
                source_urls=["https://example.com"],
            ),
        ],
    )


class TestRunPersona:
    @patch("eval.runner.subprocess.run")
    def test_run_populates_artifacts(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        persona = _make_persona()
        cache_dir = tmp_path / "cache"

        artifacts = run_persona(
            persona=persona,
            run_id="20260101_120000",
            cache_dir=cache_dir,
        )

        assert artifacts.persona_id == "persona_test"
        assert artifacts.run_id == "20260101_120000"
        assert artifacts.exit_code == 0
        assert artifacts.report_json.exists()
        assert artifacts.audit_json.exists()

        # Verify log files were created
        assert (cache_dir / "20260101_120000" / "persona_test" / "agent_stdout.log").exists()
        assert (cache_dir / "20260101_120000" / "persona_test" / "agent_stderr.log").exists()

    @patch("eval.runner.subprocess.run")
    def test_nonzero_exit_code_handled(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        persona = _make_persona()
        artifacts = run_persona(
            persona=persona,
            run_id="20260101_120001",
            cache_dir=tmp_path / "cache",
        )

        assert artifacts.exit_code == 1
        assert artifacts.report_json.exists()
        assert artifacts.audit_json.exists()


class TestReplayPersona:
    def test_replay_from_cache(self, tmp_path: Path) -> None:
        persona = _make_persona()
        run_dir = tmp_path / "cache" / "20260101_120000" / "persona_test"
        run_dir.mkdir(parents=True)

        report_data = {
            "run_id": "eval_20260101_120000_persona_test",
            "budget_used": {
                "used_dollars": 1.5,
                "used_iterations": 3,
                "used_search_calls": 10,
            },
        }
        audit_lines = [
            json.dumps({"node": "planner", "dollars": 0.5}),
            json.dumps({
                "type": "cost_summary",
                "total_dollars": 1.5,
                "iterations": 3,
                "total_search_calls": 10,
            }),
        ]

        (run_dir / "report.json").write_text(json.dumps(report_data))
        (run_dir / "audit.json").write_text("\n".join(audit_lines))
        (run_dir / "match_cache.json").write_text("{}")

        artifacts = replay_persona(persona, run_dir)

        assert artifacts.persona_id == "persona_test"
        assert artifacts.run_id == "20260101_120000"
        assert artifacts.cost_dollars == 1.5
        assert artifacts.iterations_used == 3
        assert artifacts.search_calls_used == 10
        assert artifacts.match_cache == run_dir / "match_cache.json"

    def test_replay_no_cache_raises(self, tmp_path: Path) -> None:
        persona = _make_persona()
        run_dir = tmp_path / "cache" / "20260101_120000" / "persona_test"
        run_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError):
            replay_persona(persona, run_dir)
