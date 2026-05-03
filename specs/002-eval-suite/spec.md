# Feature Specification: Evaluation Suite

**Feature Branch**: `002-eval-suite`  
**Created**: 2026-05-03  
**Status**: Draft  
**Input**: User description: "Build the Evaluation Suite for the Deep Research Agent"

## Clarifications

### Session 2026-05-03

- Q: How should replay mode handle semantic matching given the "zero API cost" guarantee? → A: Cache all match results (including embeddings) during the initial run; replay reads from the match cache.
- Q: What threshold should risk recall meet for a pass badge? → A: 100% of planted risks must be surfaced (small denominators of 1-2 per persona make partial thresholds misleading).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Author a Synthetic Persona (Priority: P1)

An engineer authors a synthetic persona by writing a YAML file that declares the target name, target context, and a list of planted facts at three difficulty tiers (easy, medium, hard) plus 1-2 planted risk patterns. The YAML is the single ground-truth source. Each planted fact includes an ID, the statement, difficulty tier, expected research dimension, match strategy, and a note explaining why it qualifies at that tier. Each planted risk includes a risk category, expected severity, and evidence source URLs.

**Why this priority**: Without well-structured personas, there is nothing to measure. Personas are the foundation of the entire eval suite.

**Independent Test**: Can be tested by validating the YAML against the `PersonaDefinition` Pydantic schema and confirming all planted facts are parseable.

**Acceptance Scenarios**:

1. **Given** a YAML file conforming to the `PersonaDefinition` schema, **When** loaded by the eval suite, **Then** it parses without error into a `PersonaDefinition` instance with all planted facts and risks intact.
2. **Given** a YAML file missing a required field (e.g., `match_strategy`), **When** loaded, **Then** a clear validation error is raised identifying the missing field.
3. **Given** three persona YAML files, **When** an engineer inspects them, **Then** each planted fact has a `notes` field explaining its difficulty tier, and each persona's name is clearly fictional (for synthetic types) or a well-documented public figure (for real_public type).

---

### User Story 2 - Deploy a Static Plant Site (Priority: P2)

An engineer deploys a static GitHub Pages site that hosts the planted facts for synthetic personas in HTML pages. Each synthetic persona has 3-6 pages of natural prose containing the planted facts, structured with semantic HTML, cross-linked, and indexed with a sitemap. The site has a prominent disclaimer on every page stating the personas are fictional and the site exists for AI evaluation purposes.

**Why this priority**: The synthetic personas' facts must be discoverable by the agent's web search layer. Without the plant site deployed, the agent cannot find synthetic persona facts, making recall measurement impossible.

**Independent Test**: Can be tested by deploying to GitHub Pages and verifying that all planted fact pages are accessible and the disclaimer is visible on every page.

**Acceptance Scenarios**:

1. **Given** the plant_site directory, **When** deployed to GitHub Pages, **Then** each synthetic persona's pages are accessible at predictable URLs and contain the planted facts in natural prose.
2. **Given** any page on the plant site, **When** viewed, **Then** a disclaimer is visible stating the personas are fictional and the site is for AI evaluation only.
3. **Given** the plant site, **When** inspected, **Then** no JavaScript, analytics, or tracking code is present. A `sitemap.xml` exists at the root.

---

### User Story 3 - Run Full Eval Suite (Priority: P1)

An engineer runs `make eval` and receives a Markdown metrics report per persona plus a combined summary. The report includes recall by tier, precision on sampled claims, confidence calibration table, risk recall, total cost incurred, and pass/fail badges against Spec 001 success criteria. The eval suite invokes the agent CLI as a subprocess for each persona.

**Why this priority**: This is the core value proposition — engineers need actionable metrics to know whether prompt or schema changes helped or hurt.

**Independent Test**: Can be tested end-to-end by running the full eval suite against all three personas and verifying the output report contains all required metrics sections.

**Acceptance Scenarios**:

1. **Given** three persona YAML files and a working agent CLI, **When** `make eval` is run, **Then** the agent is invoked once per persona via subprocess, and a per-persona Markdown report plus combined summary is written to `eval/reports/{run_id}/`.
2. **Given** a completed eval run, **When** the report is inspected, **Then** it includes: recall by tier (easy/medium/hard), precision with sample disclosure, confidence calibration table with ECE, risk recall per planted risk, cost summary (dollars/tokens/search calls), and pass/fail badges.
3. **Given** a run where the agent exhausts its budget, **When** the eval suite reports, **Then** it treats budget exhaustion as a finding, not a suite failure.

---

### User Story 4 - Run a Single Persona (Priority: P2)

An engineer runs `make eval ARGS="--persona persona_synthetic_a"` to iterate on a single persona without re-running the entire suite.

**Why this priority**: Fast iteration loops are critical during prompt tuning. Running all three personas for every tweak wastes time and money.

**Independent Test**: Can be tested by running the eval for a single persona and verifying only that persona's report is generated.

**Acceptance Scenarios**:

1. **Given** a `--persona` flag with a valid persona ID, **When** the eval runner executes, **Then** only that persona is run, and only its report is generated.
2. **Given** a `--persona` flag with an invalid ID, **When** the eval runner executes, **Then** a clear error message lists available persona IDs.

---

### User Story 5 - Replay Metrics from Cached Artifacts (Priority: P2)

An engineer runs `make eval-replay RUN_ID=...` to recompute metrics from a previous run's captured artifacts (report.json, audit.json) without re-invoking the agent. This enables fast confidence-formula tuning without incurring API costs.

**Why this priority**: Scoring formula changes are frequent during tuning. Re-running the agent for each formula tweak is wasteful when the raw artifacts haven't changed.

**Independent Test**: Can be tested by replaying from cached artifacts and verifying zero API calls are made, metrics are recomputed in under 30 seconds, and results match the expected recalculation.

**Acceptance Scenarios**:

1. **Given** a previous run's artifacts and match results cached in a known directory, **When** `--replay-from <run_id>` is used, **Then** metrics are recomputed from the cached artifacts and match cache with zero agent invocations and zero API cost (including zero embedding API calls).
2. **Given** a replay run, **When** timed, **Then** it completes in under 30 seconds.
3. **Given** a replay with a nonexistent run_id, **When** executed, **Then** a clear error message is shown.

---

### User Story 6 - Add a New Persona (Priority: P3)

A new engineer adds a fourth persona by following AUTHORING.md and the template YAML, without needing to read the runner code. The guide covers persona schema, difficulty-tier definitions, match-strategy choices, plant-site page structure, and how to run the eval for the new persona.

**Why this priority**: Extensibility matters for long-term value, but three personas are sufficient for the initial delivery.

**Independent Test**: Can be tested by having someone unfamiliar with the codebase follow AUTHORING.md to create a persona, then verifying it loads and runs correctly.

**Acceptance Scenarios**:

1. **Given** AUTHORING.md and `_template.yaml`, **When** a new engineer follows the guide, **Then** they can create a valid persona YAML, add plant-site pages, and run `make eval --persona <new_id>` within one hour.
2. **Given** a persona created from the template, **When** loaded by the eval suite, **Then** it validates against the schema without errors.

---

### Edge Cases

- What happens when the agent produces no claims for a persona? The metrics report shows 0% recall across all tiers, 0 precision (no claims to sample), and flags this as a finding.
- What happens when the agent's report.json is malformed? The runner logs the parse error, marks the persona as "agent error," and continues with other personas.
- What happens when a planted fact uses `semantic` match strategy but the embedding model is unavailable? The matcher falls back to `fuzzy` matching and logs a warning.
- What happens when `--replay-from` points to an incomplete run? The replay reports metrics only for the data available and flags which personas are missing.
- What happens when total eval cost would exceed USD 15? The suite asks for user confirmation before proceeding.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define `PersonaDefinition`, `PlantedFact`, and `PlantedRisk` Pydantic schemas in `eval/schemas.py` with all fields specified in the feature description (id, target_name, target_context, persona_type, planted_facts, planted_risks, description, ethical_notes, plant_site_root for PersonaDefinition; id, statement, difficulty, expected_dimension, expected_min_confidence, fact_type, match_strategy, match_threshold, notes, source_urls for PlantedFact; id, risk_category, expected_severity, description, evidence_source_urls for PlantedRisk).
- **FR-002**: System MUST define a `ResearchDimension` enum in `eval/schemas.py` with values: biographical, professional_history, financial_connections, network, public_statements, risk_surface.
- **FR-003**: System MUST provide three persona YAML files: `persona_synthetic_a.yaml` (~12 planted facts, 1 risk), `persona_synthetic_b.yaml` (~10 planted facts, 2 risks including 1 inconsistency), and `persona_real_public.yaml` (real public figure with source URLs per fact).
- **FR-004**: System MUST provide `eval/plant_site/` with one microsite per synthetic persona (3-6 HTML pages each), semantic HTML, cross-links, sitemap.xml, and a disclaimer on every page.
- **FR-005**: System MUST implement `eval/runner.py` with a `run_persona()` function that invokes the agent CLI as a subprocess, captures stdout/stderr, copies report.json and audit.json to the eval cache, and returns artifact paths. Match result persistence (including embedding vectors) is the responsibility of `eval/matcher.py`, which writes match_cache.json to the run's cache directory.
- **FR-006**: System MUST implement `eval/matcher.py` with three matching strategies: exact (normalized string equality), fuzzy (rapidfuzz partial_ratio above configurable threshold, default 80), and semantic (cosine similarity above configurable threshold, default 0.75, using a small embedding model). If the embedding model is unavailable (API error or missing `OPENAI_API_KEY`), the semantic strategy MUST fall back to fuzzy matching and log a warning.
- **FR-007**: System MUST implement `eval/metrics.py` with functions: `recall_by_tier()`, `precision()`, `confidence_calibration()`, `risk_recall()`, and `cost_summary()`.
- **FR-008**: System MUST implement `eval/reporter.py` that emits per-persona Markdown reports and a combined summary at `eval/reports/{run_id}/`, including calibration tables and pass/fail badges against Spec 001 success criteria.
- **FR-009**: System MUST implement `eval/cli.py` with subcommands: `python -m eval run [--persona ID] [--cache-dir DIR]`, `python -m eval replay --run-id ID [--cache-dir DIR]`, `python -m eval list-personas`, and `python -m eval validate-persona --persona ID [--all]`.
- **FR-010**: System MUST add `make eval` and `make eval-replay RUN_ID=...` targets to the Makefile.
- **FR-011**: System MUST provide `eval/personas/_template.yaml` and `eval/AUTHORING.md` for onboarding new persona authors.
- **FR-012**: Synthetic persona names MUST be clearly fictional and not collide with real public figures.
- **FR-013**: The real-public-figure persona MUST cite specific source URLs for each planted fact so a grader can independently verify ground truth.
- **FR-014**: The eval suite MUST import shared types (Claim, ValidatedClaim, RiskFlag, RiskCategory, RiskSeverity) from `src/research_agent/schemas.py` and MUST NOT modify them.
- **FR-015**: Replay mode MUST recompute metrics from cached artifacts and cached match results without invoking the agent or any external API, incurring zero API cost. Match results (including embedding vectors for semantic matching) are persisted during the initial run and read from cache during replay.
- **FR-016**: The eval suite MUST have its own budget cap; if running all personas would exceed USD 15, it MUST ask for user confirmation.
- **FR-017**: The plant site MUST contain no JavaScript, analytics, or tracking code.

### Key Entities

- **PersonaDefinition**: A complete test persona including target identity, planted ground-truth facts and risks, source URLs, and metadata. Links to PlantedFact and PlantedRisk.
- **PlantedFact**: A single ground-truth fact about a persona, with difficulty tier, expected research dimension, match strategy, and notes explaining tier assignment.
- **PlantedRisk**: A ground-truth risk pattern planted for a persona, with category, severity, description, and evidence sources.
- **RunArtifacts**: Paths to the agent's output artifacts (report.json, audit.json) for a given persona run, plus metadata like run_id and timing.
- **MetricsReport**: The computed metrics for a persona run — recall by tier, precision, calibration, risk recall, cost — plus pass/fail status against success criteria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Three persona definition files exist and validate against the PersonaDefinition schema without errors.
- **SC-002**: The plant site is deployable to a static hosting service and serves the two synthetic microsites with all planted facts accessible.
- **SC-003**: A full eval run across all three personas completes in under 30 minutes total wall time.
- **SC-004**: Each per-persona metrics report includes recall by tier, precision with sample disclosure, confidence calibration table with ECE, risk recall per planted risk, and cost summary.
- **SC-005**: Reports include clear pass/fail badges for each Spec 001 success criterion: claims with confidence > 0.8 achieve >= 95% precision, recall of easy-tier facts >= 80%, and 100% of planted risk patterns are surfaced.
- **SC-006**: Replay mode recomputes metrics from cached artifacts in under 30 seconds with zero API cost.
- **SC-007**: A new engineer can add a fourth persona within one hour by following AUTHORING.md and the template, without reading runner code.
- **SC-008**: The real-public-figure persona's planted facts are each tied to a cited source URL that a grader can independently verify.

## Assumptions

- The agent CLI (`python -m research_agent run --target "Name" [--context "..."] --output <dir>`) is stable and produces `report.json` and `audit.json` conforming to existing Pydantic schemas in `src/research_agent/schemas.py`.
- The GitHub Pages deployment for plant_site is automated via a `make deploy-plant-site` target that pushes to a `gh-pages` branch.
- The `rapidfuzz` library is an acceptable new dependency for fuzzy matching (lightweight, no heavy transitive deps).
- The `openai` SDK (already in the project) provides access to `text-embedding-3-small` for semantic matching.
- Engineers running the eval suite have API keys configured in `.env` for the agent's providers (search, LLM) and for the embedding model used by semantic matching.
- The eval suite does not need to support concurrent runs against the same cache directory.
- The existing eval scaffold files (runner.py, metrics.py, persona YAMLs, plant_site) will be fully rewritten, not extended.
- Satya Nadella remains the real-public-figure persona choice, with facts restructured to the new schema.
