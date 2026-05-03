# Implementation Plan: Evaluation Suite

**Branch**: `002-eval-suite` | **Date**: 2026-05-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-eval-suite/spec.md`

## Summary

Build a standalone evaluation suite that measures the Deep Research Agent's ability to recover planted facts and risk patterns from three test personas. The suite invokes the agent via its CLI as a subprocess, compares output claims against ground truth using three matching strategies (exact, fuzzy, semantic), and produces Markdown metrics reports with pass/fail badges. A static plant site hosts synthetic persona facts for web-search discoverability. All existing eval scaffold files are fully rewritten.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pydantic >=2.0 (schemas), pyyaml (persona loading), rapidfuzz (fuzzy matching), openai >=1.50 (embeddings via text-embedding-3-small), jinja2 (report templates), structlog (logging)
**Storage**: Filesystem (YAML personas, JSON artifacts, Markdown reports, JSON match cache)
**Testing**: pytest + pytest-asyncio (unit tests with mocked embeddings/subprocess)
**Target Platform**: macOS/Linux CLI
**Project Type**: CLI evaluation tool (read-only companion to the agent)
**Performance Goals**: Full 3-persona run < 30 min wall time; replay < 30 sec
**Constraints**: Zero API cost in replay mode; eval suite never modifies agent code/prompts; total eval budget cap USD 15
**Scale/Scope**: 3 personas, ~34 planted facts total, 4 planted risks total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| P1 — Ethical scope | PASS | Synthetic personas use clearly fictional names; real persona uses only public-source facts with citations; plant site has disclaimers on every page; no PII synthesis |
| P2 — Every claim is provenanced | PASS | Eval suite validates agent claims against provenance requirements; it does not generate claims itself |
| P3 — Prompts are code | N/A | Eval suite has no runtime LLM prompts; it only measures agent output |
| P4 — Budgets enforced in state | PASS | Runner respects agent's existing budget defaults; eval suite has its own USD 15 cap with confirmation prompt |
| P5 — Evals drive confidence | PASS | This IS the eval suite — three personas, four metrics, planted ground truth |
| P6 — Observability | PASS | Match results, cost summaries, and per-persona logs are persisted; audit.json captured from agent runs |
| P7 — Types over strings | PASS | All eval schemas are Pydantic v2; shared types imported from research_agent.schemas; no untyped dicts cross module boundaries |
| P8 — Build what we can defend | PASS | Three matching strategies have clear rationales; each architectural choice documented in research.md |
| P9 — Guardrails layered | PASS | Persona YAML validated on load; agent output validated on parse; plant site has no JS/tracking |
| P10 — No fabrication | PASS | Eval suite measures coverage gaps; does not fill them |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-eval-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
eval/
├── __init__.py                    # package init (rewritten)
├── __main__.py                    # python -m eval entry point (new)
├── cli.py                         # argparse CLI: run, replay, list-personas, validate
├── schemas.py                     # PersonaDefinition, PlantedFact, PlantedRisk,
│                                  # RunArtifacts, FactMatch, RiskMatch,
│                                  # CalibrationBucket, PersonaMetrics, MetricsReport
├── runner.py                      # run_persona() subprocess invocation, replay_persona()
├── matcher.py                     # exact / fuzzy / semantic match strategies
├── metrics.py                     # recall, precision, calibration, risk recall, cost
├── reporter.py                    # Markdown report rendering with Jinja2 templates
├── templates/
│   ├── persona_report.md.j2       # per-persona Markdown template
│   └── combined_report.md.j2      # combined summary template
├── personas/
│   ├── _template.yaml             # annotated template for new personas
│   ├── persona_synthetic_a.yaml   # Aria Vellinor (~12 facts, 1 risk)
│   ├── persona_synthetic_b.yaml   # Dorian Ashcroft (~10 facts, 2 risks)
│   └── persona_real_public.yaml   # Satya Nadella (restructured, cited)
├── plant_site/
│   ├── index.html                 # disclaimer + persona index
│   ├── sitemap.xml                # sitemap for search indexing
│   ├── _shared/
│   │   └── style.css              # minimal styling
│   ├── aria-vellinor/
│   │   ├── index.html             # biography
│   │   ├── career.html            # career timeline
│   │   ├── ventures.html          # companies founded/advised
│   │   ├── press.html             # news mentions
│   │   └── speaking.html          # conference appearances
│   └── dorian-ashcroft/
│       ├── index.html             # biography
│       ├── about.html             # background and education
│       ├── portfolio.html         # investment portfolio
│       └── filings.html           # regulatory filings
├── AUTHORING.md                   # guide for adding new personas
├── reports/                       # gitignored except .gitkeep
│   └── .gitkeep
└── cache/                         # gitignored; match results + artifact copies
    └── .gitkeep

tests/unit/
├── test_eval_schemas.py           # schema validation tests
├── test_matcher.py                # matcher unit tests (exact, fuzzy, mocked semantic)
├── test_metrics.py                # metrics computation tests with known inputs
└── test_runner.py                 # runner tests with mocked subprocess
```

**Structure Decision**: The eval suite lives entirely within `eval/` at the repo root, parallel to `src/`. It imports shared types from `src/research_agent/schemas.py` but has its own schemas, CLI, and test files. This separation enforces the read-only boundary: the eval suite never touches agent code. Tests for eval live in `tests/unit/` alongside existing agent tests, following project convention.

## Architecture

### Data Flow

```
persona.yaml → runner.py (subprocess → agent CLI) → report.json + audit.json
                                                          ↓
                                                    matcher.py (compare claims vs planted facts)
                                                          ↓
                                                    metrics.py (recall, precision, calibration, risk)
                                                          ↓
                                                    reporter.py → eval/reports/{run_id}/*.md
```

### Replay Flow

```
cached report.json + audit.json + match_cache.json
          ↓
    matcher.py (reads from match_cache.json, no API calls)
          ↓
    metrics.py → reporter.py → eval/reports/{run_id}/*.md
```

### Key Design Decisions

**1. Subprocess CLI invocation (not graph.ainvoke)**
- Rationale: The eval suite must test the agent as a black box, including CLI argument parsing, output file writing, and error handling. Direct graph invocation skips these layers and couples the eval to internal APIs.
- Rejected: `from research_agent.graph import build_graph` — couples eval to agent internals, bypasses CLI error handling, makes the eval suite fragile to refactors.

**2. Three-strategy matching (not keyword overlap)**
- Rationale: Different fact types require different matching. "Founded Vellinor Capital in 2019" needs exact or fuzzy matching. "Advocated for transparent AI governance" needs semantic matching because the agent may paraphrase.
- Rejected: Keyword overlap (current scaffold) — produces false positives on common words and misses paraphrases.

**3. Match result caching for replay**
- Rationale: Embedding API calls during matching are the only external cost. Caching match results (including embedding vectors) enables zero-cost replay for confidence formula tuning.
- Rejected: Re-computing embeddings on replay — violates the zero-API-cost guarantee.

**4. Jinja2 templates for reports (not string concatenation)**
- Rationale: Reports have complex formatting (calibration tables, pass/fail badges, ASCII charts). Jinja2 separates content from layout and is easier to maintain.
- Rejected: f-string concatenation — becomes unreadable for multi-section Markdown with tables.

**5. Clearly fictional persona names**
- Rationale: "Alexandra Chen" and "Marcus Okonkwo" are common real-world names that could collide with actual public figures. "Aria Vellinor" and "Dorian Ashcroft" are distinctive enough to avoid collisions.
- Rejected: Keeping existing names — violates FR-012 and N5.

**6. Per-fact match_strategy and match_threshold**
- Rationale: A single global threshold produces poor results because different fact types have different semantic similarity profiles. Per-fact configuration lets persona authors tune matching to the fact's expected expression.
- Rejected: Global threshold — one size doesn't fit all fact types.

### Module Responsibilities

| Module | Responsibility | Imports from agent |
|--------|---------------|-------------------|
| `eval/schemas.py` | Eval-specific Pydantic models | `RiskCategory`, `RiskSeverity` from `research_agent.schemas` |
| `eval/runner.py` | Subprocess invocation, artifact collection, match caching | None (invokes CLI as subprocess) |
| `eval/matcher.py` | Compare agent claims against planted facts using 3 strategies | `ValidatedClaim`, `RiskFlag` from `research_agent.schemas` |
| `eval/metrics.py` | Compute recall, precision, calibration, risk recall, cost | None (operates on eval schemas) |
| `eval/reporter.py` | Render Markdown reports from metrics | None |
| `eval/cli.py` | Argparse CLI entry point | None (delegates to runner/metrics/reporter) |

### Claim-to-Fact Comparison

The matcher constructs a comparison string from agent claims: `"{subject} {predicate} {object}"`. This concatenation is compared against the planted fact's `statement` field using the strategy specified per fact:

- **exact**: Both strings normalized (lowercase, stripped punctuation), then equality check
- **fuzzy**: `rapidfuzz.fuzz.partial_ratio(statement, claim_text)` >= fact's `match_threshold` (default 80)
- **semantic**: Cosine similarity of `text-embedding-3-small` embeddings >= fact's `match_threshold` (default 0.75)

### Dependency Additions

| Package | Purpose | Justification |
|---------|---------|---------------|
| `pyyaml` | Load persona YAML files | Standard YAML parser; no alternatives needed |
| `rapidfuzz` | Fuzzy string matching | Faster and more accurate than `fuzzywuzzy`; MIT licensed; no C compilation issues |
| `jinja2` | Markdown report templates | Already widely used; cleaner than string concatenation for complex reports |

Note: `openai` (already a project dependency) provides `text-embedding-3-small` for semantic matching. No new dependency needed for embeddings.

### Personas

**Persona A — Aria Vellinor (synthetic)**
- Profile: Former fintech executive turned venture capitalist, based in a fictional city-state. Founded Vellinor Capital. Board member of fictional companies.
- ~12 planted facts across tiers: 4 easy (name, role, company founded), 4 medium (board memberships, investment amounts), 4 hard (advisory relationships, conference statements requiring cross-referencing)
- 1 planted risk: REGULATORY — fictional regulatory inquiry by a fictional authority
- All supporting organizations and people are fictional

**Persona B — Dorian Ashcroft (synthetic)**
- Profile: UK-based energy sector investor with interests in fictional African markets. Chairman of fictional Ashcroft Energy Holdings.
- ~10 planted facts: 3 easy, 4 medium, 3 hard
- 2 planted risks: NETWORK (connection to a fictional sanctioned entity), INCONSISTENCY (conflicting statements about a business relationship planted across different pages)
- All supporting organizations and people are fictional

**Persona C — Satya Nadella (real public)**
- Profile: Chairman and CEO of Microsoft
- ~10 planted facts from publicly verifiable sources, each with source URL
- No planted risks (tests the agent's precision and no-fabrication discipline)
- Facts sourced from tier-1 and tier-2 public sources (SEC filings, Microsoft press releases, verified news outlets)

### Success Criteria Mapping

| Success Criterion | Pass Condition | Metric Function |
|-------------------|---------------|-----------------|
| High-confidence precision | Claims with confidence > 0.8 achieve >= 95% precision | `confidence_calibration()` checks the (0.8, 1.0] bucket |
| Easy-tier recall | >= 80% of easy-tier planted facts recovered | `recall_by_tier()["easy"]` |
| Risk recall | 100% of planted risks surfaced | `risk_recall()` |

## Phasing

### Phase 0: Schemas & Persona Authoring (Day 4 morning)
1. Write `eval/schemas.py` with all Pydantic models
2. Write `eval/personas/_template.yaml`
3. Author three persona YAML files
4. Write schema validation unit tests (`tests/unit/test_eval_schemas.py`)

### Phase 1: Plant Site & Matching (Day 4 morning–afternoon)
5. Build `eval/plant_site/` HTML pages for both synthetic personas
6. Write `eval/matcher.py` with exact/fuzzy/semantic strategies
7. Write matcher unit tests (`tests/unit/test_matcher.py`)

### Phase 2: Metrics & Runner (Day 4 afternoon)
8. Write `eval/metrics.py` with all metric functions
9. Write metrics unit tests (`tests/unit/test_metrics.py`)
10. Write `eval/runner.py` with subprocess invocation and replay
11. Write runner unit tests (`tests/unit/test_runner.py`)

### Phase 3: Reporter, CLI & Integration (Day 4 afternoon – Day 5 morning)
12. Write `eval/templates/*.md.j2` Jinja2 report templates
13. Write `eval/reporter.py`
14. Write `eval/cli.py` and `eval/__main__.py`
15. Update Makefile with eval targets
16. Write `eval/AUTHORING.md`
17. Update pyproject.toml with new dependencies
18. Update .gitignore for eval/reports/ and eval/cache/

### Phase 4: Validation & First Run (Day 5 morning)
19. Run `make eval` end-to-end
20. Review metrics report; identify agent tuning opportunities
21. Verify replay mode works with zero API cost
22. Verify plant site is deployable
