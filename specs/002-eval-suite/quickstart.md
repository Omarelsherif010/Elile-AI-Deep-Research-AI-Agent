# Quickstart: Evaluation Suite

**Date**: 2026-05-03 | **Branch**: `002-eval-suite`

## Prerequisites

1. Project installed: `make install`
2. `.env` configured with API keys (same keys as the agent, plus `OPENAI_API_KEY` for semantic matching embeddings)
3. Plant site deployed (for synthetic persona eval): `make deploy-plant-site`

## Run the Full Eval Suite

```bash
make eval
```

Runs all three personas sequentially, produces per-persona Markdown reports and a combined summary at `eval/reports/{run_id}/`.

## Run a Single Persona

```bash
make eval ARGS="--persona persona_synthetic_a"
```

## Replay Metrics from a Previous Run

```bash
make eval-replay RUN_ID=20260503_143022
```

Recomputes metrics from cached artifacts. Zero API cost. Completes in < 30 seconds.

## Validate Persona Files

```bash
make validate-personas
```

Checks all persona YAML files against the PersonaDefinition schema without running the agent.

## Add a New Persona

See `eval/AUTHORING.md` for the full guide. Quick version:

1. Copy `eval/personas/_template.yaml` to `eval/personas/persona_my_new.yaml`
2. Fill in target info, planted facts, and planted risks
3. For synthetic personas: add HTML pages to `eval/plant_site/my-persona/`
4. Validate: `python -m eval validate-persona --persona persona_my_new`
5. Run: `make eval ARGS="--persona persona_my_new"`

## View Reports

Reports are written to `eval/reports/{run_id}/`:
- `summary.md` — combined metrics across all personas with pass/fail badges
- `{persona_id}.md` — per-persona detailed report with calibration table
- `metrics.json` — machine-readable MetricsReport
- `precision_sample.json` — sampled claims for manual precision review

## CLI Reference

```bash
python -m eval run [--persona ID] [--cache-dir DIR]
python -m eval replay --run-id ID [--cache-dir DIR]
python -m eval list-personas
python -m eval validate-persona --persona ID
```
