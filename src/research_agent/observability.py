from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from research_agent.schemas import AuditEntry, RetryRecord

logger = structlog.get_logger()


class AuditLogger:
    """Write per-node execution entries to a JSONL audit file."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.audit_file = run_dir / "audit.json"
        run_dir.mkdir(parents=True, exist_ok=True)

    def log_node(
        self,
        node: str,
        input_state: dict,
        prompt_filled: str,
        raw_response: str,
        parsed_output: Any,
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        dollars: float,
        retries: list[RetryRecord] | None = None,
    ) -> AuditEntry:
        """Write a node execution entry to the audit JSONL file."""
        entry = AuditEntry(
            timestamp=datetime.now(UTC),
            node=node,
            input_state_hash=hash_state(input_state),
            prompt_filled=prompt_filled,
            raw_response=raw_response,
            parsed_output=_to_dict(parsed_output),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            dollars=dollars,
            retries=retries or [],
        )
        self._append(entry.model_dump(mode="json"))
        logger.info(
            "audit_node_logged",
            node=node,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            dollars=dollars,
        )
        return entry

    def log_cost_summary(
        self,
        total_tokens: int,
        total_dollars: float,
        total_search_calls: int,
        iterations: int,
    ) -> None:
        """Append final cost summary entry to audit log."""
        summary = {
            "type": "cost_summary",
            "timestamp": datetime.now(UTC).isoformat(),
            "total_tokens": total_tokens,
            "total_dollars": round(total_dollars, 6),
            "total_search_calls": total_search_calls,
            "iterations": iterations,
        }
        self._append(summary)
        logger.info(
            "audit_cost_summary",
            total_tokens=total_tokens,
            total_dollars=total_dollars,
            total_search_calls=total_search_calls,
            iterations=iterations,
        )

    def _append(self, data: dict) -> None:
        """Append a single JSON object as a new line in the audit JSONL file."""
        with self.audit_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, default=str) + "\n")


def hash_state(state: dict) -> str:
    """Compute sha256 of state dict (excluding mutable large fields).

    Excludes audit_entries, search_turns, claims, and validated_claims which are
    large and change frequently; the hash is used to detect structural state changes.
    """
    small = {
        k: v
        for k, v in state.items()
        if k not in ("audit_entries", "search_turns", "claims", "validated_claims")
    }
    return hashlib.sha256(json.dumps(small, sort_keys=True, default=str).encode()).hexdigest()[:16]


def traceable(node_name: str) -> Callable:
    """Decorator that adds LangSmith @traceable if LANGSMITH_API_KEY is set, else no-op."""

    def decorator(func: Callable) -> Callable:
        import os

        try:
            from langsmith import traceable as ls_traceable

            if os.getenv("LANGSMITH_API_KEY"):
                return ls_traceable(name=node_name)(func)
        except ImportError:
            pass
        return func

    return decorator


def _to_dict(value: Any) -> dict:
    """Convert a parsed output value to a plain dict for JSON serialisation."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    # Fallback: wrap in a generic container
    return {"value": str(value)}
