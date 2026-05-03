# CLI Contract: eval

**Date**: 2026-05-03

## Entry Point

```
python -m eval <command> [options]
```

## Commands

### `run`

Execute the eval suite against one or all personas.

```
python -m eval run [--persona ID] [--cache-dir DIR]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--persona` | str | (all) | Run only this persona ID |
| `--cache-dir` | path | `eval/cache` | Directory for cached artifacts |

**Behavior**:
- Without `--persona`: runs all personas found in `eval/personas/*.yaml`
- Invokes the agent CLI as a subprocess per persona
- Copies agent artifacts to cache directory
- Computes metrics and writes reports to `eval/reports/{run_id}/`
- Prints summary table to stdout
- Exit code 0 on success, 1 on error

**Budget check**: Before running, sums `max_dollars` across all personas to be run. If total exceeds USD 15, prompts for confirmation on stderr.

### `replay`

Recompute metrics from cached artifacts without invoking the agent.

```
python -m eval replay --run-id ID [--cache-dir DIR]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--run-id` | str | (required) | ID of the previous run to replay |
| `--cache-dir` | path | `eval/cache` | Directory containing cached artifacts |

**Behavior**:
- Reads report.json, audit.json, and match_cache.json from cache
- Recomputes metrics using current scoring formulas
- Writes new reports to `eval/reports/{run_id}-replay-{timestamp}/`
- Zero API cost
- Exit code 0 on success, 1 if run_id not found

### `list-personas`

List all available persona definitions.

```
python -m eval list-personas
```

**Output**: Table with columns: ID, Type, Name, Facts, Risks

### `validate-persona`

Validate a persona YAML against the schema.

```
python -m eval validate-persona --persona ID [--all]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--persona` | str | (required unless --all) | Persona ID to validate |
| `--all` | flag | false | Validate all personas in `eval/personas/` |

**Behavior**:
- Loads YAML and validates against PersonaDefinition schema
- For synthetic personas, checks that plant_site_root is set
- With `--all`, validates every `*.yaml` file in `eval/personas/` (excluding `_template.yaml`)
- Reports validation errors or success
- Exit code 0 on valid, 1 on invalid

## Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make eval` | `uv run python -m eval run $(ARGS)` | Run eval suite |
| `make eval-replay` | `uv run python -m eval replay --run-id $(RUN_ID)` | Replay metrics |
| `make validate-personas` | `uv run python -m eval validate-persona --all` | Validate all YAMLs |
| `make deploy-plant-site` | `git subtree push --prefix eval/plant_site origin gh-pages` | Deploy to GitHub Pages |

## Output Structure

```
eval/reports/{run_id}/
├── summary.md              # Combined report with pass/fail badges
├── persona_synthetic_a.md  # Per-persona report
├── persona_synthetic_b.md
├── persona_real_public.md
├── metrics.json            # Machine-readable MetricsReport
└── precision_sample.json   # Sampled claims for manual review
```
