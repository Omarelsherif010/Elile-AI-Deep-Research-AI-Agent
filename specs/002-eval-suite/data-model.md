# Data Model: Evaluation Suite

**Date**: 2026-05-03 | **Branch**: `002-eval-suite`

## Entity Relationship Diagram

```
PersonaDefinition (1) ──── (N) PlantedFact
                  (1) ──── (N) PlantedRisk

RunArtifacts (1) ──── (1) PersonaDefinition
             (1) ──── (N) FactMatch
             (1) ──── (N) RiskMatch

PersonaMetrics (1) ──── (N) FactMatch
               (1) ──── (N) RiskMatch
               (1) ──── (N) CalibrationBucket

MetricsReport (1) ──── (N) PersonaMetrics
```

## Entities

### Enums (eval/schemas.py)

| Enum | Values | Notes |
|------|--------|-------|
| `Tier` | easy, medium, hard | Difficulty tier for planted facts |
| `ResearchDimension` | biographical, professional_history, financial_connections, network, public_statements, risk_surface | Mirrors planner prompt dimensions |
| `FactType` | biographical, role, financial, network, statement, risk | Classification of fact content |
| `MatchStrategy` | exact, fuzzy, semantic | How to match agent claims against this fact |
| `PersonaType` | synthetic, real_public | Whether facts are on the plant site or from public sources |

### Enums (imported from research_agent.schemas)

| Enum | Values | Source |
|------|--------|--------|
| `RiskCategory` | REGULATORY, REPUTATIONAL, NETWORK, FINANCIAL, INCONSISTENCY, COVERAGE_GAP, OTHER | `src/research_agent/schemas.py` |
| `RiskSeverity` | LOW, MEDIUM, HIGH, CRITICAL | `src/research_agent/schemas.py` |

### PlantedFact

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| id | str | yes | — | Pattern: `fact_[a-z]\d{2}` (e.g., `fact_a01`) |
| statement | str | yes | — | Non-empty, max 500 chars |
| difficulty | Tier | yes | — | — |
| expected_dimension | ResearchDimension | yes | — | — |
| expected_min_confidence | float | no | 0.5 | Range [0.0, 1.0] |
| fact_type | FactType | yes | — | — |
| match_strategy | MatchStrategy | no | fuzzy | — |
| match_threshold | float | no | 80.0 | For fuzzy: [0, 100]; for semantic: [0.0, 1.0] |
| notes | str | yes | — | Explains why this fact is at this tier |
| source_urls | list[str] | yes | — | Min 1 URL; plant_site URLs for synthetic, real URLs for real_public |

### PlantedRisk

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| id | str | yes | — | Pattern: `risk_[a-z]\d{2}` |
| risk_category | RiskCategory | yes | — | Imported from research_agent.schemas |
| expected_severity | RiskSeverity | yes | — | Imported from research_agent.schemas |
| description | str | yes | — | Non-empty |
| evidence_source_urls | list[str] | yes | — | Min 1 URL |

### PersonaDefinition

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| id | str | yes | — | Pattern: `persona_[a-z_]+` |
| target_name | str | yes | — | Non-empty, max 200 chars |
| target_context | str | yes | — | Non-empty |
| persona_type | PersonaType | yes | — | — |
| description | str | yes | — | — |
| ethical_notes | str | yes | — | — |
| planted_facts | list[PlantedFact] | yes | — | Min 1 fact |
| planted_risks | list[PlantedRisk] | no | [] | — |
| plant_site_root | str or None | no | None | Required if persona_type == synthetic |

### RunArtifacts

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| persona_id | str | yes | — | — |
| run_id | str | yes | — | — |
| agent_run_dir | Path | yes | — | Must exist |
| report_json | Path | yes | — | Must exist, valid JSON |
| audit_json | Path | yes | — | Must exist, valid JSON |
| graph_export | Path or None | no | None | — |
| match_cache | Path or None | no | None | Path to match_cache.json |
| cost_dollars | float | yes | — | >= 0 |
| duration_seconds | float | yes | — | >= 0 |
| iterations_used | int | yes | — | >= 0 |
| search_calls_used | int | yes | — | >= 0 |
| exit_code | int | yes | — | — |

### FactMatch

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| planted_fact_id | str | yes | — | References PlantedFact.id |
| matched_claim_id | str or None | yes | — | None if fact not recovered |
| match_strategy_used | MatchStrategy | yes | — | — |
| match_score | float | yes | — | [0, 100] for fuzzy; [0.0, 1.0] for exact/semantic |
| matched_claim_confidence | float or None | yes | — | None if no match |
| matched_claim_text | str or None | no | None | For reporting/debugging |
| notes | str or None | no | None | — |

### RiskMatch

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| planted_risk_id | str | yes | — | References PlantedRisk.id |
| matched_flag_index | int or None | yes | — | Index into agent's risk_flags list; None if not found |
| matched_category | RiskCategory or None | no | None | — |
| severity_match | bool | yes | — | Whether severity matches expected |
| notes | str or None | no | None | — |

### CalibrationBucket

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| range_low | float | yes | — | [0.0, 1.0) |
| range_high | float | yes | — | (0.0, 1.0] |
| claim_count | int | yes | — | >= 0 |
| matched_count | int | yes | — | >= 0, <= claim_count |
| observed_precision | float or None | yes | — | None if claim_count == 0 |

### PersonaMetrics

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| persona_id | str | yes | — | — |
| recall_by_tier | dict[Tier, float] | yes | — | Keys: easy, medium, hard |
| precision | float | yes | — | [0.0, 1.0] |
| precision_sample_size | int | yes | — | — |
| precision_is_automated | bool | yes | — | True for synthetic, False for real_public |
| risk_recall | float | yes | — | [0.0, 1.0] |
| fact_matches | list[FactMatch] | yes | — | — |
| risk_matches | list[RiskMatch] | yes | — | — |
| calibration_buckets | list[CalibrationBucket] | yes | — | Exactly 5 buckets |
| expected_calibration_error | float | yes | — | [0.0, 1.0] |
| cost_dollars | float | yes | — | >= 0 |
| duration_seconds | float | yes | — | >= 0 |
| success_criteria | dict[str, bool] | yes | — | Named criterion -> pass/fail |

### MetricsReport

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| run_id | str | yes | — | — |
| timestamp | datetime | yes | — | — |
| per_persona | list[PersonaMetrics] | yes | — | — |
| overall_pass | bool | yes | — | True only if all personas pass all criteria |
| total_cost_dollars | float | yes | — | >= 0 |
| total_duration_seconds | float | yes | — | >= 0 |

## State Transitions

The eval suite has a simple linear flow with no branching state machine:

```
YAML loaded → Agent invoked → Artifacts collected → Claims matched →
Metrics computed → Report rendered
```

For replay:

```
Cached artifacts loaded → Match cache loaded → Metrics recomputed →
Report rendered
```

No state transitions require tracking — each step produces output consumed by the next.

## File System Artifacts

| Path | Created by | Contents |
|------|-----------|----------|
| `eval/cache/{run_id}/{persona_id}/report.json` | runner | Copy of agent's report output |
| `eval/cache/{run_id}/{persona_id}/audit.json` | runner | Copy of agent's audit log |
| `eval/cache/{run_id}/{persona_id}/match_cache.json` | matcher | Match results + embedding vectors |
| `eval/cache/{run_id}/{persona_id}/agent_stdout.log` | runner | Agent subprocess stdout |
| `eval/cache/{run_id}/{persona_id}/agent_stderr.log` | runner | Agent subprocess stderr |
| `eval/reports/{run_id}/{persona_id}.md` | reporter | Per-persona Markdown report |
| `eval/reports/{run_id}/summary.md` | reporter | Combined summary report |
| `eval/reports/{run_id}/precision_sample.json` | metrics | Sampled claims for manual review |
| `eval/reports/{run_id}/metrics.json` | reporter | Machine-readable MetricsReport |
