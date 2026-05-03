"""Integration test: verify audit log has all 8 axes for each node entry."""

from __future__ import annotations

import json
from pathlib import Path

from research_agent.observability import AuditLogger, hash_state

# ---------------------------------------------------------------------------
# Core 8-axes contract
# ---------------------------------------------------------------------------


def test_audit_logger_writes_all_8_axes(tmp_path: Path) -> None:
    """Every log_node() call must persist all 8 observation axes plus retries."""
    audit = AuditLogger(tmp_path)
    audit.log_node(
        node="test_node",
        input_state={"run_id": "test", "iteration": 1},
        prompt_filled="test prompt",
        raw_response="test response",
        parsed_output={"key": "value"},
        latency_ms=100.0,
        tokens_in=500,
        tokens_out=200,
        dollars=0.01,
    )

    lines = (tmp_path / "audit.json").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, "Expected exactly one JSONL entry"

    entry = json.loads(lines[0])

    required_axes = [
        "timestamp",
        "node",
        "input_state_hash",
        "prompt_filled",
        "raw_response",
        "parsed_output",
        "latency_ms",
        "tokens_in",
        "tokens_out",
        "dollars",
        "retries",
    ]
    for axis in required_axes:
        assert axis in entry, f"Missing axis: {axis}"


# ---------------------------------------------------------------------------
# Multiple entries — each on its own line (JSONL)
# ---------------------------------------------------------------------------


def test_audit_logger_multiple_entries(tmp_path: Path) -> None:
    """Three successive log_node() calls must produce three independent JSONL lines."""
    audit = AuditLogger(tmp_path)
    for i in range(3):
        audit.log_node(
            node=f"node_{i}",
            input_state={},
            prompt_filled="",
            raw_response="",
            parsed_output={},
            latency_ms=10.0,
            tokens_in=10,
            tokens_out=5,
            dollars=0.001,
        )

    lines = (tmp_path / "audit.json").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3, f"Expected 3 JSONL lines, got {len(lines)}"

    # Each line must be independently parseable JSON.
    for line in lines:
        json.loads(line)


# ---------------------------------------------------------------------------
# Cost summary entry
# ---------------------------------------------------------------------------


def test_cost_summary_entry(tmp_path: Path) -> None:
    """log_cost_summary() must append a type=cost_summary entry with all fields."""
    audit = AuditLogger(tmp_path)
    audit.log_cost_summary(
        total_tokens=1000,
        total_dollars=0.05,
        total_search_calls=20,
        iterations=3,
    )

    lines = (tmp_path / "audit.json").read_text(encoding="utf-8").strip().splitlines()
    summary = json.loads(lines[-1])

    assert summary["type"] == "cost_summary"
    assert "total_tokens" in summary
    assert "total_dollars" in summary
    assert "total_search_calls" in summary
    assert "iterations" in summary


# ---------------------------------------------------------------------------
# hash_state behaviour
# ---------------------------------------------------------------------------


def test_hash_state_excludes_large_fields() -> None:
    """Large mutable fields must not affect the hash so it stays stable across iterations."""
    state1 = {
        "run_id": "abc",
        "iteration": 1,
        "audit_entries": ["big", "list"],
        "claims": [{"id": "x"}],
    }
    state2 = {
        "run_id": "abc",
        "iteration": 1,
        "audit_entries": ["different", "entries"],
    }
    assert hash_state(state1) == hash_state(state2)


def test_hash_state_changes_on_meaningful_diff() -> None:
    """A change to a non-excluded field must produce a different hash."""
    state1 = {"run_id": "abc", "iteration": 1}
    state2 = {"run_id": "abc", "iteration": 2}
    assert hash_state(state1) != hash_state(state2)


def test_hash_state_returns_16_char_hex() -> None:
    """hash_state() must return a 16-character hex string."""
    result = hash_state({"run_id": "x", "iteration": 0})
    assert len(result) == 16
    assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# Retries round-trip
# ---------------------------------------------------------------------------


def test_audit_logger_records_retries(tmp_path: Path) -> None:
    """Retry records passed to log_node() must be persisted in the JSONL entry."""
    from research_agent.schemas import RetryRecord

    audit = AuditLogger(tmp_path)
    retries = [
        RetryRecord(attempt=1, reason="timeout", latency_ms=250.0),
        RetryRecord(attempt=2, reason="rate_limit", latency_ms=300.0),
    ]
    audit.log_node(
        node="flaky_node",
        input_state={"run_id": "r1"},
        prompt_filled="p",
        raw_response="r",
        parsed_output={},
        latency_ms=550.0,
        tokens_in=100,
        tokens_out=50,
        dollars=0.005,
        retries=retries,
    )

    entry = json.loads(
        (tmp_path / "audit.json").read_text(encoding="utf-8").strip().splitlines()[0]
    )
    assert len(entry["retries"]) == 2
    assert entry["retries"][0]["reason"] == "timeout"
    assert entry["retries"][1]["reason"] == "rate_limit"
