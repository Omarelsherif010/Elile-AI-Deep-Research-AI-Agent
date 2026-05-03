# Research: Evaluation Suite

**Date**: 2026-05-03 | **Branch**: `002-eval-suite`

## R1: Fuzzy String Matching Library

**Decision**: Use `rapidfuzz` for fuzzy string matching.

**Rationale**: rapidfuzz is a drop-in replacement for fuzzywuzzy with 10-50x better performance, MIT licensed, and actively maintained. It provides `partial_ratio` which handles substring matching well (useful when agent claims contain extra context around a planted fact). Pre-compiled C extensions mean no runtime compilation issues.

**Alternatives considered**:
- `fuzzywuzzy`: Slower, GPL-licensed (python-Levenshtein dependency), less actively maintained.
- `thefuzz`: Fork of fuzzywuzzy with same performance characteristics; rapidfuzz is strictly better.
- Custom Levenshtein: Unnecessary complexity when rapidfuzz exists.

## R2: Semantic Matching Approach

**Decision**: Use OpenAI `text-embedding-3-small` via the existing `openai` SDK dependency.

**Rationale**: The project already depends on `openai >= 1.50`. Using text-embedding-3-small keeps the embedding provider consistent with the rest of the project. The model is cheap ($0.02/1M tokens), produces 1536-dimensional vectors, and handles the short-text similarity task well. Embeddings are cached alongside run artifacts so replay mode incurs zero API cost.

**Alternatives considered**:
- `sentence-transformers` (local): Would add a large dependency (~500MB+ with torch). Overkill for matching ~30 claims against ~12 planted facts per persona. Also adds GPU/CPU compatibility concerns.
- `text-embedding-3-large`: More dimensions (3072), higher cost, no meaningful accuracy improvement for short-text similarity at this scale.

## R3: Report Template Engine

**Decision**: Use `jinja2` for Markdown report templates.

**Rationale**: Reports include calibration tables, pass/fail badges, per-fact match details, and ASCII bar charts. String concatenation becomes unreadable fast. Jinja2 is the standard Python template engine, well-known, and lightweight. Templates live in `eval/templates/` and are version-controlled.

**Alternatives considered**:
- f-strings / string concatenation: Works for simple reports but becomes error-prone with multi-section Markdown tables and conditional content.
- `mako`: Less widely known, no meaningful advantage over Jinja2 for this use case.

## R4: Match Result Caching Strategy

**Decision**: Persist match results as `match_cache.json` in the run's cache directory. The cache contains: per-fact match results (planted_fact_id, matched_claim_id, score, strategy), per-risk match results, and embedding vectors (base64-encoded float arrays).

**Rationale**: The clarification from the spec requires replay mode to have zero API cost. Since semantic matching calls the embedding API, match results must be cached during the initial run. Storing the cache as JSON alongside `report.json` and `audit.json` keeps all run artifacts co-located. Embedding vectors are included so that if the matching formula changes (but not the embedding model), replay can recompute similarity scores without re-embedding.

**Alternatives considered**:
- Cache only final match booleans (not scores/vectors): Would prevent re-scoring with different thresholds during replay. The whole point of replay is to re-tune scoring.
- SQLite cache: Overkill for ~50 records per run. JSON is simpler and human-inspectable.

## R5: Plant Site Deployment

**Decision**: Use `git subtree push` via a `make deploy-plant-site` target to push `eval/plant_site/` to the `gh-pages` branch.

**Rationale**: GitHub Pages serves static content from a designated branch. `git subtree push` is a single command that pushes a subdirectory to a branch without requiring a separate repository or CI pipeline. The plant site is pure HTML/CSS with no build step.

**Alternatives considered**:
- GitHub Actions for deployment: Adds CI complexity that's out of scope for v1. The project explicitly excludes CI/CD.
- Separate repository for plant site: Adds maintenance overhead. Keeping it in-repo under `eval/plant_site/` is simpler.

## R6: Precision Measurement Approach

**Decision**: For synthetic personas, compute precision automatically by checking whether each sampled agent claim matches any planted fact (using fuzzy matching as a liberal check). For the real-public persona, sample claims and persist them for manual review, reporting precision as "pending manual review" until labeled.

**Rationale**: Fully automated precision for synthetic personas is possible because we control the full set of planted facts. For real public figures, the fact universe is too large to enumerate — automated checking would produce false negatives (marking correct claims as incorrect because they weren't in the planted set). The precision sample is persisted to `precision_sample.json` so a human reviewer can label claims and replay metrics.

**Alternatives considered**:
- Fully manual precision for all personas: Slower iteration; defeats the purpose of automated eval for synthetic personas.
- LLM-as-judge for precision: Adds cost and non-determinism; we want deterministic metrics for A/B comparisons.

## R7: Confidence Calibration (ECE)

**Decision**: Use Expected Calibration Error (ECE) with 5 equal-width bins: (0.0, 0.2], (0.2, 0.4], (0.4, 0.6], (0.6, 0.8], (0.8, 1.0].

**Rationale**: ECE is the standard calibration metric in the ML literature. Five bins provide enough resolution to spot miscalibration patterns (e.g., overconfident claims) without being so granular that bins have too few samples. For each bin, observed precision is the fraction of claims in that confidence range that matched a planted fact. ECE = weighted average of |observed_precision - bin_midpoint| across bins.

**Alternatives considered**:
- Adaptive Calibration Error (ACE): Uses equal-mass bins. Better for skewed distributions but harder to interpret in a fixed report format.
- 10 bins: Too granular for ~30-50 claims per persona; most bins would be empty.

## R8: Existing Scaffold Rewrite Strategy

**Decision**: Fully rewrite all existing eval files. Do not extend or patch.

**Rationale**: The existing scaffold has fundamental architectural issues: direct graph invocation instead of subprocess CLI, keyword-overlap matching instead of three-strategy matching, wrong persona schema format, real organization names in synthetic personas, and no replay capability. Extending would require changing every function signature and data structure. A clean rewrite is faster and produces cleaner code.

**Files to rewrite**: `eval/runner.py`, `eval/metrics.py`, `eval/personas/*.yaml`, `eval/plant_site/*`.
**Files to add**: `eval/schemas.py`, `eval/matcher.py`, `eval/reporter.py`, `eval/cli.py`, `eval/__main__.py`, `eval/templates/`, `eval/AUTHORING.md`, `eval/personas/_template.yaml`.
