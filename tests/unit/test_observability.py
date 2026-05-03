from __future__ import annotations

import json
from pathlib import Path

from research_agent.observability import AuditLogger, hash_state
from research_agent.schemas import RetryRecord


class TestAuditLogger:
    def test_creates_audit_file_on_first_log(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run1")
        audit_logger.log_node(
            node="planner",
            input_state={"target": "Jane Doe"},
            prompt_filled="Plan for Jane Doe",
            raw_response='{"plan": "..."}',
            parsed_output={"plan": "..."},
            latency_ms=150.0,
            tokens_in=100,
            tokens_out=200,
            dollars=0.005,
        )
        assert audit_logger.audit_file.exists()

    def test_single_entry_is_valid_json(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run2")
        audit_logger.log_node(
            node="extractor",
            input_state={},
            prompt_filled="extract claims",
            raw_response="[]",
            parsed_output=[],
            latency_ms=80.0,
            tokens_in=50,
            tokens_out=30,
            dollars=0.001,
        )
        lines = audit_logger.audit_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["node"] == "extractor"

    def test_multiple_log_node_calls_produce_multiple_lines(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run3")
        for i in range(3):
            audit_logger.log_node(
                node=f"node_{i}",
                input_state={"i": i},
                prompt_filled=f"prompt {i}",
                raw_response=f"response {i}",
                parsed_output={"result": i},
                latency_ms=float(i * 10),
                tokens_in=i * 100,
                tokens_out=i * 50,
                dollars=float(i) * 0.001,
            )
        lines = audit_logger.audit_file.read_text().strip().splitlines()
        assert len(lines) == 3
        nodes = [json.loads(line)["node"] for line in lines]
        assert nodes == ["node_0", "node_1", "node_2"]

    def test_entry_contains_all_audit_fields(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run4")
        audit_logger.log_node(
            node="validator",
            input_state={"key": "val"},
            prompt_filled="validate this",
            raw_response="validated",
            parsed_output={"ok": True},
            latency_ms=99.9,
            tokens_in=111,
            tokens_out=222,
            dollars=0.01,
        )
        entry = json.loads(audit_logger.audit_file.read_text().strip())
        required_keys = {
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
        }
        assert required_keys.issubset(entry.keys())

    def test_retries_recorded(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run5")
        retries = [RetryRecord(attempt=1, reason="timeout", latency_ms=500.0)]
        audit_logger.log_node(
            node="reflector",
            input_state={},
            prompt_filled="reflect",
            raw_response="ok",
            parsed_output={},
            latency_ms=600.0,
            tokens_in=10,
            tokens_out=10,
            dollars=0.0,
            retries=retries,
        )
        entry = json.loads(audit_logger.audit_file.read_text().strip())
        assert len(entry["retries"]) == 1
        assert entry["retries"][0]["reason"] == "timeout"

    def test_log_cost_summary_appends_entry(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run6")
        audit_logger.log_cost_summary(
            total_tokens=5000,
            total_dollars=0.25,
            total_search_calls=10,
            iterations=3,
        )
        lines = audit_logger.audit_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["type"] == "cost_summary"
        assert entry["total_tokens"] == 5000
        assert entry["total_dollars"] == 0.25
        assert entry["total_search_calls"] == 10
        assert entry["iterations"] == 3

    def test_log_cost_summary_after_nodes(self, tmp_path: Path) -> None:
        audit_logger = AuditLogger(run_dir=tmp_path / "run7")
        audit_logger.log_node(
            node="planner",
            input_state={},
            prompt_filled="plan",
            raw_response="ok",
            parsed_output={},
            latency_ms=10.0,
            tokens_in=10,
            tokens_out=10,
            dollars=0.0,
        )
        audit_logger.log_cost_summary(1000, 0.10, 5, 2)
        lines = audit_logger.audit_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_run_dir_created_automatically(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "run"
        AuditLogger(run_dir=nested)
        assert nested.exists()


class TestHashState:
    def test_deterministic(self) -> None:
        state = {"target": "Jane Doe", "budget": {"max_dollars": 5.0}}
        h1 = hash_state(state)
        h2 = hash_state(state)
        assert h1 == h2

    def test_excludes_audit_entries(self) -> None:
        state_a = {"target": "Jane", "audit_entries": [{"node": "planner"}]}
        state_b = {"target": "Jane", "audit_entries": []}
        assert hash_state(state_a) == hash_state(state_b)

    def test_excludes_search_turns(self) -> None:
        state_a = {"target": "Jane", "search_turns": [{"query": "foo"}]}
        state_b = {"target": "Jane", "search_turns": []}
        assert hash_state(state_a) == hash_state(state_b)

    def test_excludes_claims(self) -> None:
        state_a = {"target": "Jane", "claims": [{"id": "abc"}]}
        state_b = {"target": "Jane", "claims": []}
        assert hash_state(state_a) == hash_state(state_b)

    def test_excludes_validated_claims(self) -> None:
        state_a = {"target": "Jane", "validated_claims": [{"confidence": 0.9}]}
        state_b = {"target": "Jane", "validated_claims": []}
        assert hash_state(state_a) == hash_state(state_b)

    def test_different_targets_produce_different_hashes(self) -> None:
        h1 = hash_state({"target": "Jane Doe"})
        h2 = hash_state({"target": "John Smith"})
        assert h1 != h2

    def test_hash_is_16_chars(self) -> None:
        h = hash_state({"target": "Jane Doe"})
        assert len(h) == 16
