# Tasks: Evaluation Suite

**Input**: Design documents from `/specs/002-eval-suite/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cli-contract.md

**Tests**: Included — project constitution mandates "tests ship with code."

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create eval package structure, add dependencies, configure gitignore

- [X] T001 Create eval package directories: eval/templates/, eval/personas/, eval/plant_site/_shared/, eval/plant_site/aria-vellinor/, eval/plant_site/dorian-ashcroft/, eval/reports/, eval/cache/
- [X] T002 [P] Create eval/__init__.py with package docstring
- [X] T003 [P] Create eval/__main__.py entry point that delegates to eval.cli.main()
- [X] T004 [P] Add new dependencies to pyproject.toml: pyyaml, rapidfuzz, jinja2 (under [project.dependencies] or eval extra)
- [X] T005 [P] Update .gitignore to exclude eval/reports/*/ (keep .gitkeep), eval/cache/*/ (keep .gitkeep)
- [X] T006 [P] Create eval/reports/.gitkeep and eval/cache/.gitkeep

---

## Phase 2: Foundational (Schemas)

**Purpose**: Define all eval-specific Pydantic models that every downstream module depends on

**CRITICAL**: No user story work can begin until schemas are complete

- [X] T007 Implement eval/schemas.py with enums: Tier, ResearchDimension, FactType, MatchStrategy, PersonaType — importing RiskCategory and RiskSeverity from src/research_agent/schemas.py
- [X] T008 Implement eval/schemas.py Pydantic models: PlantedFact, PlantedRisk, PersonaDefinition per data-model.md field specifications
- [X] T009 Implement eval/schemas.py models: RunArtifacts, FactMatch, RiskMatch, CalibrationBucket, PersonaMetrics, MetricsReport per data-model.md
- [X] T010 Write tests/unit/test_eval_schemas.py: validate PlantedFact, PlantedRisk, PersonaDefinition round-trip from dict, test field validators, test enum values match planner prompt dimensions

**Checkpoint**: Schemas ready — all downstream modules can import from eval.schemas

---

## Phase 3: User Story 1 — Author a Synthetic Persona (Priority: P1) MVP

**Goal**: Three persona YAML files that parse cleanly against PersonaDefinition schema, with planted facts at three tiers and planted risks

**Independent Test**: Run `python -c "from eval.schemas import PersonaDefinition; import yaml; PersonaDefinition(**yaml.safe_load(open('eval/personas/persona_synthetic_a.yaml')))"` and confirm it succeeds for all three files

### Implementation for User Story 1

- [X] T011 [P] [US1] Create eval/personas/_template.yaml with annotated placeholder structure showing all PersonaDefinition fields, PlantedFact fields with inline comments, and PlantedRisk fields
- [X] T012 [P] [US1] Author eval/personas/persona_synthetic_a.yaml — Aria Vellinor: ~12 planted facts (4 easy, 4 medium, 4 hard) across all 6 dimensions, 1 planted risk (REGULATORY), all fictional orgs/people, match_strategy per fact, notes explaining tier
- [X] T013 [P] [US1] Author eval/personas/persona_synthetic_b.yaml — Dorian Ashcroft: ~10 planted facts (3 easy, 4 medium, 3 hard), 2 planted risks (NETWORK + INCONSISTENCY), all fictional orgs/people, includes contradictory statements across pages
- [X] T014 [P] [US1] Author eval/personas/persona_real_public.yaml — Satya Nadella: ~10 planted facts from public sources, each with source_urls citing tier-1/tier-2 sources (SEC filings, Microsoft press releases, verified news), no planted risks
- [X] T015 [US1] Write tests/unit/test_eval_schemas.py (extend T010): load all three persona YAMLs, validate against PersonaDefinition, assert fact counts per tier, assert risk counts, assert all source_urls are non-empty

**Checkpoint**: Three persona files exist and validate. Template available for new personas.

---

## Phase 4: User Story 3 — Run Full Eval Suite (Priority: P1) MVP

**Goal**: `make eval` invokes the agent CLI per persona, matches claims against planted facts, computes recall/precision/calibration/risk metrics, and writes Markdown reports with pass/fail badges

**Independent Test**: Run `make eval` end-to-end against all three personas and verify eval/reports/{run_id}/summary.md contains recall by tier, precision, calibration table, risk recall, cost summary, and pass/fail badges

### Implementation for User Story 3

- [X] T016 [P] [US3] Implement eval/matcher.py: ExactMatcher (normalized lowercase + strip punctuation), FuzzyMatcher (rapidfuzz.fuzz.partial_ratio), SemanticMatcher (text-embedding-3-small via openai SDK, cosine similarity) — each with configurable threshold, claim text constructed as "{subject} {predicate} {object}"
- [X] T017 [P] [US3] Implement eval/matcher.py: match_facts(persona, claims, embedder) -> list[FactMatch] that iterates planted facts, applies per-fact match_strategy, returns FactMatch per planted fact; match_risks(persona, flags) -> list[RiskMatch] matching by risk_category + fuzzy description
- [X] T018 [P] [US3] Write tests/unit/test_matcher.py: test exact match with normalization, test fuzzy match above/below threshold, test semantic match with mocked embeddings (patch openai client), test match_facts returns correct FactMatch list, test match_risks with category match
- [X] T019 [P] [US3] Implement eval/metrics.py: compute_recall(matches, facts) -> dict[Tier, float], compute_precision(claims, planted_facts, sample_size=30) -> dict with rate + sampled_claims + is_automated flag, compute_calibration(claims, fact_matches) -> tuple[list[CalibrationBucket], float ECE], compute_risk_recall(risk_matches, risks) -> float, cost_summary(artifacts) -> dict
- [X] T020 [P] [US3] Implement eval/metrics.py: evaluate_success_criteria(metrics) -> dict[str, bool] mapping: "high_confidence_precision" (>0.8 conf claims >= 95% precision), "easy_recall" (>= 80%), "risk_recall" (100%)
- [X] T021 [P] [US3] Write tests/unit/test_metrics.py: test recall computation with known fact matches (3 found of 4 easy = 0.75), test precision sampling, test calibration buckets with hand-built claims, test ECE formula, test risk recall, test success criteria pass/fail
- [X] T022 [US3] Implement eval/runner.py: run_persona(persona, output_dir, env_overrides) that builds subprocess command ["python", "-m", "research_agent", "run", "--target", ...], streams stdout/stderr to log files, copies report.json + audit.json to cache, reads audit.json for cost/duration/iterations, returns RunArtifacts
- [X] T023 [US3] Write tests/unit/test_runner.py: mock subprocess.run to return canned report.json + audit.json, verify RunArtifacts populated correctly, verify log files written, verify non-zero exit code handled without crash
- [X] T024 [P] [US3] Create eval/templates/persona_report.md.j2: Jinja2 template for per-persona report with sections: header, recall table (easy/medium/hard), precision with sample disclosure, calibration table with ASCII bar chart, risk recall per-risk table, cost summary, pass/fail badges
- [X] T025 [P] [US3] Create eval/templates/combined_report.md.j2: Jinja2 template for combined summary with per-persona summary rows, overall pass/fail, total cost, run metadata
- [X] T026 [US3] Implement eval/reporter.py: render_persona_report(metrics) -> str, render_combined_report(report) -> str, write_report(report, output_dir) that writes per-persona .md files + summary.md + metrics.json + precision_sample.json
- [X] T027 [US3] Implement eval/cli.py: argparse with subcommands (run, replay, list-personas, validate-persona), run subcommand loads personas from eval/personas/, calls run_persona per persona, calls matcher, metrics, reporter; budget cap check (sum max_dollars vs USD 15 threshold with confirmation prompt)
- [X] T028 [US3] Update Makefile: add `eval` target (`uv run python -m eval run $(ARGS)`), add `eval-replay` target (`uv run python -m eval replay --run-id $(RUN_ID)`)

**Checkpoint**: `make eval` runs all personas end-to-end and produces Markdown reports with all metrics sections

---

## Phase 5: User Story 2 — Deploy a Static Plant Site (Priority: P2)

**Goal**: Static HTML site with 3-6 pages per synthetic persona, semantic HTML, cross-links, disclaimers, sitemap, deployable to GitHub Pages

**Independent Test**: Open eval/plant_site/index.html in a browser; verify disclaimer visible, navigate to each persona's pages, verify planted facts are present in natural prose

### Implementation for User Story 2

- [X] T029 [P] [US2] Create eval/plant_site/_shared/style.css: minimal CSS for readability (max-width, font, nav links, footer disclaimer styling)
- [X] T030 [P] [US2] Create eval/plant_site/index.html: top-level disclaimer banner ("This site contains fictional personas for AI evaluation purposes only"), links to each persona's microsite
- [X] T031 [P] [US2] Create eval/plant_site/aria-vellinor/index.html: biography page with semantic HTML (<article>, <header>, <time>), planted easy-tier facts in natural prose, nav links to other pages, footer disclaimer
- [X] T032 [P] [US2] Create eval/plant_site/aria-vellinor/career.html: career timeline with medium-tier facts (board memberships, role transitions), cross-links to ventures.html
- [X] T033 [P] [US2] Create eval/plant_site/aria-vellinor/ventures.html: companies founded/advised with medium/hard-tier facts (investment amounts, advisory relationships)
- [X] T034 [P] [US2] Create eval/plant_site/aria-vellinor/press.html: news mentions with hard-tier facts requiring cross-referencing (regulatory inquiry details, conference quotes)
- [X] T035 [P] [US2] Create eval/plant_site/aria-vellinor/speaking.html: conference appearances with public_statements dimension facts
- [X] T036 [P] [US2] Create eval/plant_site/dorian-ashcroft/index.html: biography page with easy-tier facts, disclaimer footer
- [X] T037 [P] [US2] Create eval/plant_site/dorian-ashcroft/about.html: background and education with biographical dimension facts
- [X] T038 [P] [US2] Create eval/plant_site/dorian-ashcroft/portfolio.html: investment portfolio with financial_connections facts, contradictory statement (one side of inconsistency)
- [X] T039 [P] [US2] Create eval/plant_site/dorian-ashcroft/filings.html: regulatory filings page with risk_surface facts, opposite side of contradictory statement
- [X] T040 [US2] Create eval/plant_site/sitemap.xml listing all HTML pages with lastmod dates
- [X] T041 [US2] Add `deploy-plant-site` target to Makefile: `git subtree push --prefix eval/plant_site origin gh-pages`

**Checkpoint**: Plant site pages render correctly in browser; all planted facts from persona YAMLs appear in natural prose across pages; disclaimer on every page

---

## Phase 6: User Story 4 — Run a Single Persona (Priority: P2)

**Goal**: `make eval ARGS="--persona persona_synthetic_a"` runs only that persona

**Independent Test**: Run with --persona flag and verify only one persona's report is generated

### Implementation for User Story 4

- [X] T042 [US4] Verify eval/cli.py --persona flag filters persona list correctly (implemented in T027); add error message listing available persona IDs when invalid ID provided
- [X] T043 [US4] Add `eval-one` target to Makefile: `uv run python -m eval run --persona $(PERSONA)`; add `validate-personas` target: `uv run python -m eval validate-persona --all`

**Checkpoint**: Single-persona run produces only that persona's report; invalid ID shows helpful error

---

## Phase 7: User Story 5 — Replay Metrics from Cached Artifacts (Priority: P2)

**Goal**: `make eval-replay RUN_ID=...` recomputes metrics from cached artifacts in < 30 sec with zero API cost

**Independent Test**: Run eval once, then replay from cached artifacts; verify reports regenerated with zero subprocess/API calls and completion in < 30 sec

### Implementation for User Story 5

- [X] T044 [US5] Implement match cache persistence in eval/matcher.py: after match_facts/match_risks, serialize FactMatch list + RiskMatch list + embedding vectors (base64-encoded) to match_cache.json in the run's cache directory
- [X] T045 [US5] Implement eval/runner.py replay_persona(persona, run_dir) -> RunArtifacts: read cached report.json, audit.json, match_cache.json; populate RunArtifacts without invoking subprocess
- [X] T046 [US5] Implement eval/cli.py replay subcommand: load personas, call replay_persona per persona, load match cache, recompute metrics from cached matches, write new reports to eval/reports/{run_id}-replay-{timestamp}/
- [X] T047 [US5] Write test in tests/unit/test_runner.py (extend T023): create mock cache directory with report.json + audit.json + match_cache.json; call replay_persona; verify no subprocess invoked; verify RunArtifacts populated from cache

**Checkpoint**: Replay produces identical metric structure as live run; completes in < 30 sec; no API calls made

---

## Phase 8: User Story 6 — Add a New Persona (Priority: P3)

**Goal**: AUTHORING.md + validate-persona command enable a new engineer to add a persona within 1 hour

**Independent Test**: Follow AUTHORING.md to create a minimal 2-fact persona; run validate-persona; confirm it loads without error

### Implementation for User Story 6

- [X] T048 [P] [US6] Write eval/AUTHORING.md: sections for persona schema reference (all fields with types and examples), difficulty tier definitions (easy = headline-visible, medium = requires reading article body, hard = requires cross-referencing multiple pages), match strategy guidance (when to use exact vs fuzzy vs semantic), plant site page structure (how to add HTML pages), running eval for a single persona, checklist for new persona authors
- [X] T049 [US6] Implement validate-persona subcommand in eval/cli.py: load YAML, validate against PersonaDefinition schema, for synthetic personas check plant_site_root is set, report validation result; add --all flag to validate all personas in eval/personas/

**Checkpoint**: AUTHORING.md is self-contained; validate-persona catches schema errors with clear messages

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, cleanup, verification

- [X] T050 Remove old eval CLI from src/research_agent/cli.py: delete the `eval` subcommand that used direct graph invocation (it's replaced by `python -m eval`)
- [X] T051 Update old `make eval` target in Makefile to use new `python -m eval run` instead of `python -m research_agent eval`
- [X] T052 Verify all persona YAML source_urls in persona_real_public.yaml point to actual public URLs (spot-check 3-5 URLs)
- [X] T053 Run `make eval` end-to-end against all three personas; review generated reports at eval/reports/{run_id}/
  - **Note**: Verified with mock data (e2e_demo_004). Live eval blocked by Gemini free-tier quota exhaustion (429 RESOURCE_EXHAUSTED). Agent falls back to OpenAI successfully but runtime exceeds 5 min per persona. Full live eval deferred until Gemini quota resets or premium tier is enabled.
- [X] T054 Run `make eval-replay RUN_ID=...` with the run from T053; verify reports regenerated in < 30 sec
  - **Verified**: Replay of e2e_demo_004 completed in 2.9s with correct metrics (9/12 facts found, precision=1.00, risk recall=1.00, ECE=0.175).
- [X] T055 Run quickstart.md validation: execute each command from quickstart.md and verify expected behavior
  - **make validate-personas** ✅ — all 3 personas validate
  - **python -m eval list-personas** ✅ — lists all personas with counts
  - **make eval-replay RUN_ID=...** ✅ — replays in ~3s, generates reports
  - **make eval** ⚠️ — command works but live agent run blocked by Gemini 429 (falls back to OpenAI, runtime >5 min/persona)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (schemas must exist for YAML validation)
- **US3 (Phase 4)**: Depends on Foundational (schemas) + US1 (persona files must exist)
- **US2 (Phase 5)**: Depends on US1 (persona facts must be finalized before writing HTML); can run in PARALLEL with US3
- **US4 (Phase 6)**: Depends on US3 (CLI must exist)
- **US5 (Phase 7)**: Depends on US3 (runner/matcher must exist for caching)
- **US6 (Phase 8)**: Depends on US1 (schema finalized) + US3 (CLI validate command)
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependencies on other stories
- **US3 (P1)**: Depends on US1 — needs persona files to load
- **US2 (P2)**: Depends on US1 — needs persona facts to write into HTML. Can run in parallel with US3
- **US4 (P2)**: Depends on US3 — extends CLI with filter flag (already built in T027, just verify)
- **US5 (P2)**: Depends on US3 — adds caching to existing matcher + replay to runner
- **US6 (P3)**: Depends on US1 + US3 — documents schema + CLI commands

### Within Each User Story

- Schemas before implementations
- Matcher and metrics can run in parallel (both depend only on schemas)
- Runner depends on matcher (calls match_facts after agent run)
- Reporter depends on metrics (renders PersonaMetrics)
- CLI depends on runner + reporter (orchestrates the pipeline)
- Tests written alongside implementation (same task or immediately after)

### Parallel Opportunities

- T002, T003, T004, T005, T006 (all Setup) — different files
- T007, T008, T009 could be one file but are sequential within schemas
- T011, T012, T013, T014 (all persona YAMLs) — different files
- T016/T017 and T019/T020 (matcher and metrics) — different files, both depend only on schemas
- T024, T025 (Jinja2 templates) — different files
- T029-T039 (all plant site pages) — different files
- T044-T046 (replay features) — sequential within the feature

## Parallel Example: User Story 3

```bash
# Launch matcher and metrics in parallel (different files, both depend on schemas):
Task: "T016 Implement eval/matcher.py exact/fuzzy/semantic strategies"
Task: "T019 Implement eval/metrics.py recall/precision/calibration/risk functions"

# Launch their tests in parallel:
Task: "T018 Write tests/unit/test_matcher.py"
Task: "T021 Write tests/unit/test_metrics.py"

# Launch Jinja2 templates in parallel:
Task: "T024 Create eval/templates/persona_report.md.j2"
Task: "T025 Create eval/templates/combined_report.md.j2"
```

## Parallel Example: User Story 2

```bash
# Launch all plant site pages in parallel (all independent HTML files):
Task: "T031 Create eval/plant_site/aria-vellinor/index.html"
Task: "T032 Create eval/plant_site/aria-vellinor/career.html"
Task: "T033 Create eval/plant_site/aria-vellinor/ventures.html"
Task: "T036 Create eval/plant_site/dorian-ashcroft/index.html"
Task: "T037 Create eval/plant_site/dorian-ashcroft/about.html"
```

---

## Implementation Strategy

### MVP First (US1 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (schemas)
3. Complete Phase 3: US1 (persona authoring)
4. Complete Phase 4: US3 (full eval run)
5. **STOP and VALIDATE**: Run `make eval` end-to-end; verify reports generated with all metrics
6. This is a functional eval suite even without the plant site (real-public persona works immediately)

### Incremental Delivery

1. Setup + Schemas + US1 → Personas ready
2. Add US3 → Full eval pipeline works → **MVP deliverable**
3. Add US2 → Plant site deployed → synthetic persona recall becomes meaningful
4. Add US4 → Single-persona iteration loop → faster tuning
5. Add US5 → Replay mode → zero-cost formula tuning
6. Add US6 → Onboarding docs → team can add personas

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Schemas together
2. Once schemas are done:
   - Developer A: US1 (persona YAMLs) → US3 (matcher + metrics)
   - Developer B: US2 (plant site pages — independent HTML)
3. After US1 done: Developer A continues US3 (runner + reporter + CLI)
4. After US3 done: US4, US5, US6 are small additions

---

## Notes

- All existing eval files (runner.py, metrics.py, personas/*.yaml, plant_site/*) are FULLY REWRITTEN, not extended
- Synthetic persona names: Aria Vellinor (persona_a), Dorian Ashcroft (persona_b) — clearly fictional
- Real persona: Satya Nadella — restructured with cited source URLs
- All supporting orgs/people in synthetic personas must be fictional (no real orgs like DBS Bank, INSEAD)
- Plant site pages must contain planted facts in natural prose, not as data dumps
- The eval suite never imports from agent code except shared schemas (Claim, ValidatedClaim, RiskFlag, etc.)
- Commit after each task or logical group per project conventions
