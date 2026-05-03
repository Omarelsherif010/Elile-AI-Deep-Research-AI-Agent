"""Eval metrics computation for the research agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvalMetrics:
    persona_name: str
    recall_easy: float = 0.0
    recall_medium: float = 0.0
    recall_hard: float = 0.0
    precision: float = 0.0
    confidence_calibration: float = 0.0
    risk_recall: float = 0.0

    # Raw counts
    easy_found: int = 0
    easy_total: int = 0
    medium_found: int = 0
    medium_total: int = 0
    hard_found: int = 0
    hard_total: int = 0
    risk_found: int = 0
    risk_total: int = 0

    def pass_fail(self, thresholds: dict[str, float]) -> dict[str, bool]:
        """Return per-dimension pass/fail against supplied thresholds."""
        return {
            "recall_easy": self.recall_easy >= thresholds.get("recall_easy", 0.70),
            "recall_medium": self.recall_medium >= thresholds.get("recall_medium", 0.50),
            "precision": self.precision >= thresholds.get("precision", 0.90),
            "confidence_calibration": self.confidence_calibration
            >= thresholds.get("confidence_calibration", 0.95),
            "risk_recall": self.risk_recall >= thresholds.get("risk_recall", 0.80),
        }

    def overall_pass(self, thresholds: dict[str, float]) -> bool:
        """Return True only if all per-dimension checks pass."""
        return all(self.pass_fail(thresholds).values())


def compute_recall(
    ground_truth: list[dict[str, Any]],
    validated_claims: list[dict[str, Any]],
    match_threshold: float = 0.7,
) -> tuple[int, int]:
    """Count how many ground truth facts appear in validated claims.

    Returns (found, total).
    Simple matching: check if gt subject+predicate+object keywords appear in any claim.
    """
    found = 0
    for gt in ground_truth:
        gt_text = f"{gt['subject']} {gt['predicate']} {gt['object']}".lower()
        gt_words = set(gt_text.split())
        for claim in validated_claims:
            claim_text = (
                f"{claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}"
            ).lower()
            claim_words = set(claim_text.split())
            overlap = len(gt_words & claim_words) / max(len(gt_words), 1)
            if overlap >= match_threshold:
                found += 1
                break
    return found, len(ground_truth)


def compute_precision(validated_claims: list[dict[str, Any]], sample_size: int = 30) -> float:
    """Estimate precision. Without human judgment, use confidence > 0.5 as proxy for correct.

    Returns fraction of sample with confidence > 0.5.
    """
    if not validated_claims:
        return 1.0
    sample = validated_claims[:sample_size]
    high_confidence = sum(1 for c in sample if c.get("confidence", 0) > 0.5)
    return high_confidence / len(sample)


def compute_confidence_calibration(validated_claims: list[dict[str, Any]]) -> float:
    """For claims with confidence > 0.8, what fraction have ≥ 2 corroborating sources?

    Uses n_supporting_sources as proxy for ground truth.
    """
    high_conf = [c for c in validated_claims if c.get("confidence", 0) > 0.8]
    if not high_conf:
        return 1.0
    well_supported = sum(1 for c in high_conf if len(c.get("supporting_sources", [])) >= 2)
    return well_supported / len(high_conf)


def compute_risk_recall(
    expected_flags: list[dict[str, Any]],
    actual_flags: list[dict[str, Any]],
    match_threshold: float = 0.5,
) -> tuple[int, int]:
    """Count how many expected risk flags were surfaced.

    Returns (found, total).
    Matching: type must match AND description keywords overlap.
    """
    found = 0
    for expected in expected_flags:
        exp_type = expected.get("type", "")
        exp_desc = expected.get("description", "").lower()
        exp_words = set(exp_desc.split())
        for actual in actual_flags:
            if actual.get("type") != exp_type:
                continue
            act_desc = actual.get("description", "").lower()
            act_words = set(act_desc.split())
            if exp_words and act_words:
                overlap = len(exp_words & act_words) / len(exp_words)
                if overlap >= match_threshold:
                    found += 1
                    break
            elif not exp_words:
                found += 1
                break
    return found, len(expected_flags)


def compute_metrics(
    persona: dict[str, Any],
    report_json: dict[str, Any],
) -> EvalMetrics:
    """Compute all metrics for a persona run."""
    gt = persona.get("ground_truth", {})

    validated_claims = report_json.get("claims", [])
    actual_flags = report_json.get("risk_flags", [])

    easy_found, easy_total = compute_recall(gt.get("easy", []), validated_claims)
    medium_found, medium_total = compute_recall(
        gt.get("medium", []), validated_claims, match_threshold=0.6
    )
    hard_found, hard_total = compute_recall(
        gt.get("hard", []), validated_claims, match_threshold=0.5
    )

    precision = compute_precision(validated_claims)
    calibration = compute_confidence_calibration(validated_claims)
    risk_found, risk_total = compute_risk_recall(
        persona.get("expected_risk_flags", []), actual_flags
    )

    return EvalMetrics(
        persona_name=persona.get("name", "unknown"),
        recall_easy=easy_found / max(easy_total, 1),
        recall_medium=medium_found / max(medium_total, 1),
        recall_hard=hard_found / max(hard_total, 1),
        precision=precision,
        confidence_calibration=calibration,
        risk_recall=risk_found / max(risk_total, 1),
        easy_found=easy_found,
        easy_total=easy_total,
        medium_found=medium_found,
        medium_total=medium_total,
        hard_found=hard_found,
        hard_total=hard_total,
        risk_found=risk_found,
        risk_total=risk_total,
    )
