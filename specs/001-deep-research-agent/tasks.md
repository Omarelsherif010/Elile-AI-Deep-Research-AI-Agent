# Tasks: Deep Research AI Agent

**Input**: Design documents from `specs/001-deep-research-agent/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/, research.md, quickstart.md

**Tests**: Tests are REQUIRED per constitution (Development Discipline: "Tests ship with code"). Unit tests are bundled with implementation tasks. Integration and end-to-end tests are separate tasks.

**Organization**: Tasks are grouped by user story. US1+US2 are combined as co-P1 stories (the provenance requirement is inseparable from the core pipeline).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US3, US4, US5)
- US2 is merged into US1 (provenance is embedded in extraction/validation/reporting)

## Phase 1: Setup

**Purpose**: Project initialization and build tooling

- [X] T001 Create project directory structure per plan.md layout (src/research_agent/, src/research_agent/nodes/, src/research_agent/tools/, prompts/, eval/, eval/personas/, eval/plant_site/, tests/unit/, tests/integration/, tests/fixtures/, runs/) including __init__.py in src/research_agent/nodes/ and src/research_agent/tools/
- [X] T002 Create pyproject.toml with all dependencies (langgraph, pydantic, anthropic, openai, google-generativeai, neo4j, httpx, tenacity, structlog, trafilatura, respx, pytest, pytest-asyncio, ruff) and project metadata in pyproject.toml
- [X] T003 [P] Create Makefile with targets: install, lint, test, test-live, run, eval, demo, clean in Makefile
- [X] T004 [P] Create .env.example with all required and optional env vars per contracts/cli.md in .env.example
- [X] T005 [P] Create .gitignore (runs/*, .env, __pycache__, *.sqlite, .ruff_cache) and runs/.gitkeep in .gitignore
- [X] T006 [P] Create src/research_agent/__init__.py with package version and src/research_agent/__main__.py with `python -m research_agent` entry point

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, tools, and infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Implement all Pydantic schemas (TargetProfile, ResearchPlan, SubQuestion, SearchResult, SearchTurn, Source, Claim, ValidatedClaim, Entity, Relation, RiskFlag, Budget, AuditEntry, RetryRecord) per data-model.md in src/research_agent/schemas.py with unit test in tests/unit/test_schemas.py
- [X] T008 [P] Implement ResearchState TypedDict with all fields per data-model.md in src/research_agent/state.py
- [X] T009 [P] Implement typed errors (BudgetExceeded, GuardrailViolation, ProviderUnavailable, SchemaValidationError) in src/research_agent/errors.py
- [X] T010 [P] Implement RiskCategory enum (7 values) and RiskSeverity enum (Low/Medium/High/Critical) in src/research_agent/risk_taxonomy.py with unit test in tests/unit/test_risk_taxonomy.py
- [X] T011 [P] Implement confidence formula (4-factor weighted: source_authority 0.35, corroboration 0.30, recency 0.15, consistency 0.20) with tier mapping and env-configurable weights in src/research_agent/confidence.py with unit test in tests/unit/test_confidence.py
- [X] T012 [P] Implement Guardrails class (validate_input, wrap_untrusted_content, filter_pii, check_output_safety) per plan guardrails section in src/research_agent/guardrails.py with unit test in tests/unit/test_guardrails.py
- [X] T013 Create prompt structural template with Role/Context/Task/OutputFormat/Constraints/Examples/Notes sections in prompts/_template.md
- [X] T014 Implement Prompt loader (parse markdown sections, render with kwargs) and LLMRouter (role-to-provider mapping, Pydantic validation, retry with feedback, 3 providers) in src/research_agent/tools/llm.py with unit test in tests/unit/test_llm.py
- [X] T015 [P] Implement CostTracker (tracks tokens in/out, dollars, search calls per provider) in src/research_agent/tools/cost.py with unit test in tests/unit/test_cost.py
- [X] T016 Implement HTTP fetch with robots.txt checking (urllib.robotparser), trafilatura fallback extraction, and content wrapping via guardrails in src/research_agent/tools/fetch.py with unit test (respx mocked) in tests/unit/test_fetch.py
- [X] T017 Implement SearchRouter with intent-to-provider mapping (Brave/Exa/Firecrawl), fallback chains, rate limiting via tenacity, and SearchCache integration in src/research_agent/tools/search.py with unit test (respx mocked) in tests/unit/test_search.py
- [X] T018 [P] Implement Neo4j writer with idempotent MERGE queries for entities and relations, graceful skip when DB unavailable in src/research_agent/tools/neo4j_writer.py with unit test (mocked driver) in tests/unit/test_neo4j_writer.py
- [X] T019 Implement SearchCache (SQLite-backed, sha256 key, TTL 7d/30d), EntityRegistry (Neo4j-backed canonical names), RunStateStore (SqliteSaver wrapper) in src/research_agent/memory.py with unit test in tests/unit/test_memory.py
- [X] T020 [P] Implement AuditLogger (per-node JSONL writer with 8 axes), LangSmith integration (@traceable decorator helper), and CostTracker glue in src/research_agent/observability.py with unit test in tests/unit/test_observability.py

**Checkpoint**: Foundation ready — all types, tools, and infrastructure available for node implementation

---

## Phase 3: US1+US2 — End-to-End Research Run + Claim Provenance (Priority: P1) MVP

**Goal**: Given a target name, the full pipeline runs and produces a report with provenanced claims, an identity graph, and an audit log — all within budget caps.

**Independent Test**: `python -m research_agent run --target "Test Person"` produces report.md, report.json, graph_export.json, audit.json, and checkpoint.sqlite. Every claim in the report links to source URLs with confidence scores.

### Prompts for US1+US2

- [X] T021 [P] [US1] Create planner prompt (generates ResearchPlan from TargetProfile; covers 6 dimensions; outputs SubQuestion list) in prompts/planner.md
- [X] T022 [P] [US1] Create query_expander prompt (expands a SubQuestion into 2-3 search query variants) in prompts/query_expander.md
- [X] T023 [P] [US1] Create extractor prompt (extracts Claim, Entity, Relation from source content; requires source_urls on every claim) in prompts/extractor.md
- [X] T024 [P] [US1] Create validator prompt (cross-references claims against sources; classifies source tiers; outputs validation notes) in prompts/validator.md
- [X] T025 [P] [US1] Create reflector prompt (evaluates progress vs budget; decides continue/pivot/terminate; outputs gap analysis) in prompts/reflector.md
- [X] T026 [P] [US1] Create reporter prompt (generates Markdown report with sections: executive summary, findings by dimension, claim inventory with provenance, scope and limitations, budget consumption) in prompts/reporter.md
- [X] T026b [P] [US1] Create risk_analyzer prompt (detects risk patterns from taxonomy, assigns 4-level severity, outputs evidence chains with claim IDs + source URLs, requires justification for OTHER category) in prompts/risk_analyzer.md
- [X] T026c [US1] Create prompt schema tests: for each prompt (planner, query_expander, extractor, validator, reflector, risk_analyzer, reporter), verify output validates against its target Pydantic schema across 3 fixture inputs in tests/unit/test_prompt_schemas.py

### Nodes for US1+US2

- [X] T027 [US1] Implement planner node (iteration 0: full plan from target; iteration >0: refine from gaps + existing claims; BudgetGuard + @traceable) in src/research_agent/nodes/planner.py with unit test in tests/unit/test_node_planner.py
- [X] T028 [US1] Implement search_orchestrator node (expand queries via LLM, route to SearchRouter by intent, cache check, budget-aware dispatch) in src/research_agent/nodes/search_orchestrator.py with unit test in tests/unit/test_node_search.py
- [X] T029 [US1] Implement extractor node (for each search result with content, call LLM to extract claims/entities/relations; wrap content via guardrails; apply PII filter) in src/research_agent/nodes/extractor.py with unit test in tests/unit/test_node_extractor.py
- [X] T030 [US1] Implement validator node (cross-reference claims, classify source tiers via LLM, compute confidence via confidence.py, enforce provenance rules: ≥2 domains or 1 Tier-1 for >0.5; label LLM-only claims as inferred) in src/research_agent/nodes/validator.py with unit test in tests/unit/test_node_validator.py
- [X] T031 [US1] Implement reflector node (evaluate dimension coverage, project remaining budget, decide continue/pivot/terminate, update gaps) in src/research_agent/nodes/reflector.py with unit test in tests/unit/test_node_reflector.py
- [X] T032 [US1] Implement graph_builder node (canonicalize entities by fuzzy name + type + attributes, dedup relations, export graph_export.json, write to Neo4j if available) in src/research_agent/nodes/graph_builder.py with unit test in tests/unit/test_node_graph_builder.py
- [X] T033 [US1] Implement risk_analyzer node (detect risk patterns from taxonomy, assign severity Low/Medium/High/Critical, generate COVERAGE_GAP flags for thin dimensions, require justification for OTHER) in src/research_agent/nodes/risk_analyzer.py with unit test in tests/unit/test_node_risk_analyzer.py
- [X] T034 [US1] Implement reporter node (generate report.md + report.json; sections per contracts/nodes.md; apply check_output_safety guardrail before write) in src/research_agent/nodes/reporter.py with unit test in tests/unit/test_node_reporter.py

### Graph Wiring + CLI

- [X] T035 [US1] Wire LangGraph StateGraph with all 8 nodes, conditional edges on reflector (continue/pivot/terminate), SqliteSaver checkpointer, BudgetGuard decorator on all nodes (enforcing iteration count, search calls, dollar cap, and per-iteration time cap from Budget) in src/research_agent/graph.py
- [X] T036 [US1] Implement CLI with argparse (run command: --target, --aliases, --role, --org, --context, --geo, --output, --max-iterations, --max-search-calls, --max-dollars; eval command; exit codes per contracts/cli.md) in src/research_agent/cli.py
- [X] T037 [US1] Create recorded LLM response fixtures and HTTP cassettes for one synthetic target in tests/fixtures/
- [ ] T038 [US1] End-to-end fixture test: full pipeline on recorded cassette, verify all 5 output files produced, verify claims have source_urls, verify confidence scores present in tests/integration/test_end_to_end.py

**Checkpoint**: US1+US2 complete. Pipeline runs end-to-end. Every claim has provenance. Budget is enforced. MVP is functional.

---

## Phase 4: US3 — Risk Flag Presentation (Priority: P2)

**Goal**: Risk flags in the report are grouped by category with severity ratings and evidence chains linking back to specific validated claims.

**Independent Test**: Run against an eval persona with planted risk patterns. Verify risk section groups by category, shows severity, and references supporting claims with source URLs.

- [ ] T039 [P] [US3] Update risk_analyzer prompt: add richer evidence chain formatting (claim text + source URLs per risk flag) and refine category-specific detection guidance for improved risk recall in prompts/risk_analyzer.md
- [ ] T040 [US3] Update reporter node to render risk flags grouped by category, sorted by severity (Critical first), with per-flag evidence chains showing claim text + source URLs in src/research_agent/nodes/reporter.py
- [ ] T041 [US3] Update report.json schema to include structured risk_flags array with category, severity, description, evidence_claim_ids, and linked source URLs in src/research_agent/nodes/reporter.py
- [ ] T042 [US3] Unit test for risk flag presentation: verify report groups by category, severity ordering, evidence chain references in tests/unit/test_risk_presentation.py

**Checkpoint**: US3 complete. Risk flags are grouped, severity-rated, and evidence-linked in both Markdown and JSON reports.

---

## Phase 5: US4 — Run Replay and Observability (Priority: P2)

**Goal**: Every processing step is reconstructable from both LangSmith traces and the local audit log, with consistent data across both.

**Independent Test**: Complete a run, open LangSmith trace, read audit.json. Verify all 8 node executions are visible in both with matching 8-axis metadata.

- [X] T043 [US4] Verify and fix AuditLogger writes all 8 axes (timestamp, node, input_state_hash, prompt_filled, raw_response, parsed_output, latency_ms, tokens, dollars, retries) for every node execution in src/research_agent/observability.py
- [X] T044 [US4] Verify and fix @traceable decorator sends matching metadata to LangSmith (same 8 axes as audit log) for every node in src/research_agent/observability.py
- [X] T045 [US4] Add cost summary to audit.json final entry (total tokens, total dollars, total search calls, iterations used) in src/research_agent/observability.py
- [X] T046 [US4] Integration test: run fixture pipeline, parse audit.json, verify every node has all 8 axes, verify cost totals are consistent in tests/integration/test_observability.py

**Checkpoint**: US4 complete. Both traces and audit log are complete, consistent, and support full run replay.

---

## Phase 6: US5 — Eval Suite Execution (Priority: P2)

**Goal**: Three eval personas with planted ground truth. The eval runner executes all three and emits a metrics report with recall, precision, confidence calibration, and risk recall.

**Independent Test**: `make eval` runs all three personas, produces a metrics report, and reports pass/fail against threshold targets.

- [X] T047 [P] [US5] Define persona_synthetic_a.yaml (synthetic persona with planted easy/medium/hard facts and risk patterns; source content hosted on plant_site) in eval/personas/persona_synthetic_a.yaml
- [X] T048 [P] [US5] Define persona_synthetic_b.yaml (second synthetic persona with different risk profile; tests different taxonomy categories) in eval/personas/persona_synthetic_b.yaml
- [X] T049 [P] [US5] Define persona_real_public.yaml (real public figure with documented history; ground truth from verifiable public records) in eval/personas/persona_real_public.yaml
- [X] T050 [P] [US5] Create plant_site static pages for synthetic personas (HTML pages with planted facts at different difficulty tiers, deployed to GitHub Pages) in eval/plant_site/
- [X] T051 [US5] Implement eval metrics computation (recall at 3 tiers, precision on sample of 30, confidence calibration for >0.8 claims, risk recall on planted patterns) in eval/metrics.py with unit test in tests/unit/test_metrics.py
- [X] T052 [US5] Implement eval runner (load persona YAML, execute pipeline per persona, collect outputs, compute metrics, emit metrics report JSON + summary) in eval/runner.py
- [X] T053 [US5] Wire eval command into CLI (`python -m research_agent eval --persona <name> --output <dir>`) in src/research_agent/cli.py
- [ ] T054 [US5] Run all three eval personas end-to-end and verify metrics meet thresholds (recall easy ≥70%, precision ≥90%, calibration ≥95%, risk recall ≥80%)

**Checkpoint**: US5 complete. Eval suite runs, measures four metrics, reports pass/fail against targets.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, demo, and final quality pass

- [X] T055 [P] Write README.md with: project overview, design decisions (with rationale + rejected alternatives), architecture diagram, quickstart, eval results, ethical scope statement
- [X] T056 [P] Verify scope-and-limitations section in reporter output meets constitutional requirements (Principle 1 bounds, public-sources-only disclaimer, no sensitive attribute inference); fix if missing or incomplete in src/research_agent/nodes/reporter.py and prompts/reporter.md
- [X] T057 [P] Run ruff check + ruff format across entire codebase; fix any violations
- [ ] T058 Execute a live target run on a well-known public figure, save output to runs/demo/ as the demo run artifact
- [X] T059 [P] Create streamlit_app.py (optional): file upload for report.json, display report sections, interactive graph visualization in streamlit_app.py
- [X] T060 Final make test + make lint pass; verify all unit and integration tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001, T002 complete) — BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Foundational phase completion — this is the MVP
- **US3 (Phase 4)**: Depends on US1+US2 (risk_analyzer node must exist)
- **US4 (Phase 5)**: Depends on US1+US2 (needs running pipeline to verify observability)
- **US5 (Phase 6)**: Depends on US1+US2 (eval runner invokes the full pipeline)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1+US2 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories. This is the MVP.
- **US3 (P2)**: Depends on US1+US2 (refines risk_analyzer and reporter nodes that already exist)
- **US4 (P2)**: Depends on US1+US2 (verifies observability infrastructure that's baked into the pipeline)
- **US5 (P2)**: Depends on US1+US2 (eval runner calls the full pipeline). Persona definitions (T047-T050) can start in parallel with US1+US2.

### Within Each Phase

- Models/schemas before tools
- Tools before nodes
- Prompts before their consuming nodes (can parallel with other prompts)
- All nodes before graph wiring
- Graph wiring before CLI
- CLI before integration tests

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004, T005, T006)
- All Foundational tasks marked [P] can run in parallel after T007 (T008-T012, T015, T018, T020)
- All prompts (T021-T026) can run in parallel
- Nodes that don't depend on each other's output can parallel (but wiring requires all)
- Eval persona definitions (T047-T050) can parallel with US1+US2 implementation
- All Polish tasks marked [P] can parallel (T055-T057, T059)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# After T007 (schemas) completes, launch these in parallel:
Task T008: "Implement ResearchState TypedDict in src/research_agent/state.py"
Task T009: "Implement typed errors in src/research_agent/errors.py"
Task T010: "Implement RiskCategory + RiskSeverity enums in src/research_agent/risk_taxonomy.py"
Task T011: "Implement confidence formula in src/research_agent/confidence.py"
Task T012: "Implement Guardrails class in src/research_agent/guardrails.py"
Task T015: "Implement CostTracker in src/research_agent/tools/cost.py"
Task T018: "Implement Neo4j writer in src/research_agent/tools/neo4j_writer.py"
Task T020: "Implement AuditLogger in src/research_agent/observability.py"
```

## Parallel Example: Phase 3 (Prompts)

```bash
# All prompts can be written in parallel:
Task T021: "Create planner prompt in prompts/planner.md"
Task T022: "Create query_expander prompt in prompts/query_expander.md"
Task T023: "Create extractor prompt in prompts/extractor.md"
Task T024: "Create validator prompt in prompts/validator.md"
Task T025: "Create reflector prompt in prompts/reflector.md"
Task T026: "Create reporter prompt in prompts/reporter.md"
Task T026b: "Create risk_analyzer prompt in prompts/risk_analyzer.md"
# Then after all prompts complete:
Task T026c: "Test all prompt schemas in tests/unit/test_prompt_schemas.py"
```

---

## Implementation Strategy

### MVP First (US1+US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1+US2
4. **STOP and VALIDATE**: Run `python -m research_agent run --target "Test Person"` and verify all 5 outputs produced
5. Deploy/demo if ready — this is a working product

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1+US2 → Test independently → First end-to-end run (MVP!)
3. Add US3 → Test risk presentation → Risk flags properly grouped and severity-rated
4. Add US4 → Verify observability → Audit logs and traces are complete and consistent
5. Add US5 → Run eval suite → Metrics meet thresholds
6. Polish → README, demo run, Streamlit, submission

### Day-by-Day Mapping

| Day | Morning | Afternoon |
|-----|---------|-----------|
| Day 1 | Phase 1 (Setup) + Phase 2 starts (T007-T012) | Phase 2 continues (T013-T020) |
| Day 2 | Phase 3 prompts (T021-T026) + nodes start (T027-T030) | Phase 3 nodes (T031-T034) + wiring (T035-T036) |
| Day 3 | Phase 3 tests (T037-T038) + Phase 4 US3 (T039-T042) | Phase 5 US4 (T043-T046) |
| Day 4 | Phase 6 US5 personas (T047-T050) + metrics (T051) | Phase 6 runner (T052-T054) |
| Day 5 | Phase 7 polish (T055-T058) | Live target run + demo prep |
| Day 6 | Streamlit (T059) if time | Demo video + submission (T060) |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [US*] label maps task to specific user story for traceability
- US1+US2 are combined because provenance (US2) is inseparable from the extraction/validation pipeline (US1)
- Each unit test is bundled with its implementation task (constitution: "tests ship with code")
- Eval personas (T047-T050) can be started early while US1 implementation is in progress
- Commit after each task or logical group using conventional commits (feat:/fix:/test:/docs:)
- Stop at any checkpoint to validate the story independently
