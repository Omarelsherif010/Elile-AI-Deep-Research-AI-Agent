# Implementation Plan: Deep Research AI Agent

**Branch**: `001-deep-research-agent` | **Date**: 2026-05-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-deep-research-agent/spec.md`

## Summary

Build a LangGraph-orchestrated multi-agent pipeline that, given a target person's name, conducts iterative web research across multiple search providers, extracts structured claims with source provenance, cross-validates them with a documented confidence formula, surfaces risk patterns from a typed taxonomy, builds an in-memory identity graph (with optional Neo4j persistence), and produces an auditable Markdown/JSON risk report. The system is multi-model (Claude Opus 4.7 for reasoning, GPT-5.4 Mini for extraction, Gemini 3 Flash for high-fanout expansion), budget-enforced, fully traced via LangSmith + local audit logs, and evaluated against three test personas with planted ground truth.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LangGraph ≥1.1, Pydantic v2, anthropic SDK, openai SDK, google-generativeai SDK, neo4j Python driver, httpx, tenacity, structlog, trafilatura
**Package Manager**: uv
**Lint/Format**: ruff (replaces black, isort, flake8)
**Storage**: Neo4j Aura free tier (graph, optional); SQLite (search cache, checkpoints); filesystem (runs/, audit logs)
**Testing**: pytest with pytest-asyncio; respx for HTTP mocking; eval suite separate in eval/
**Target Platform**: macOS / Linux (developer workstation; no deployment target)
**Project Type**: CLI tool + eval harness + optional Streamlit demo
**Performance Goals**: End-to-end run completes in ~10 minutes; budget caps are the hard limits (≤8 iterations, ≤60 search calls, ≤USD 5)
**Constraints**: Multi-model routing (3 providers); public sources only; no PII synthesis; robots.txt respected
**Scale/Scope**: Single-user CLI; one target per run; ~50-200 claims per run; ~20-100 entities in graph

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Ethical scope is non-negotiable | ✅ PASS | `guardrails.py` validates input, wraps untrusted content, filters PII. `fetch.py` respects robots.txt. No sensitive attribute inference. Every report includes scope section. |
| 2 | Every claim is provenanced | ✅ PASS | `Claim` schema requires `source_urls`. `ValidatedClaim` enforces ≥2 domains or 1 Tier-1 for confidence >0.5. LLM-only claims capped at 0.4 and labeled. |
| 3 | Prompts are code | ✅ PASS | All prompts in `prompts/*.md` with Role/Context/Task/OutputFormat/Constraints/Examples/Notes. Loaded by `tools/llm.py:Prompt`, never inlined. Version-controlled. |
| 4 | Budgets are enforced in state | ✅ PASS | `Budget` in `ResearchState` with 4 caps. `BudgetGuard` decorator on every node. Reflector checks remaining budget. Graceful termination to reporter. |
| 5 | Evals drive confidence | ✅ PASS | 3 personas in `eval/personas/`. `eval/runner.py` + `eval/metrics.py` measure recall, precision, calibration, risk recall. Gated on prompt changes. |
| 6 | Observability is first-class | ✅ PASS | LangSmith tracing on every node (`@traceable`). `AuditLogger` writes 8-axis JSON per node. `CostTracker` in state. All three layers always on. |
| 7 | Types over strings | ✅ PASS | All inter-node data is Pydantic v2. `schemas.py` defines every model. LLMs classify/extract/synthesize; Python does routing/scoring/graph writes. |
| 8 | We build what we can defend in 8 minutes | ✅ PASS | `research.md` documents every decision with rationale + rejected alternative. README "Design decisions" section. |
| 9 | Guardrails are layered | ✅ PASS | 4 chokepoints: target ingestion (`validate_input`), fetch (`wrap_untrusted_content`), extraction (`filter_pii`), report (`check_output_safety`). |
| 10 | No fabrication | ✅ PASS | Reporter writes "coverage gap" finding when data is thin. Zero-claim termination documented with queries/providers attempted. No plausible filler. |

**Gate result**: ALL PASS. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-deep-research-agent/
├── plan.md              # This file
├── research.md          # Phase 0: technology decisions
├── data-model.md        # Phase 1: Pydantic schemas + state
├── quickstart.md        # Phase 1: setup and first run
├── contracts/
│   ├── cli.md           # CLI interface contract
│   └── nodes.md         # Node input/output contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/research_agent/
├── __init__.py
├── cli.py                          # argparse entry point
├── schemas.py                      # all Pydantic models
├── state.py                        # ResearchState TypedDict
├── graph.py                        # LangGraph StateGraph wiring
├── confidence.py                   # multi-factor scoring formula
├── risk_taxonomy.py                # RiskCategory enum + severity
├── guardrails.py                   # input/output validation, PII filter
├── memory.py                       # SearchCache, EntityRegistry, RunStateStore
├── observability.py                # AuditLogger + LangSmith + CostTracker
├── errors.py                       # typed exceptions
├── nodes/
│   ├── __init__.py
│   ├── planner.py                  # generates/refines ResearchPlan
│   ├── search_orchestrator.py      # dispatches queries to SearchRouter
│   ├── extractor.py                # extracts claims + entities from content
│   ├── validator.py                # cross-validates claims, assigns confidence
│   ├── reflector.py                # decides continue/pivot/terminate
│   ├── graph_builder.py            # builds in-memory graph + Neo4j write
│   ├── risk_analyzer.py            # detects risk patterns from taxonomy
│   └── reporter.py                 # produces report.md + report.json
└── tools/
    ├── __init__.py
    ├── search.py                   # SearchRouter (Brave, Exa, Firecrawl)
    ├── fetch.py                    # HTTP fetch + robots.txt + trafilatura
    ├── llm.py                      # Prompt loader + LLMRouter (3 providers)
    ├── neo4j_writer.py             # idempotent MERGE writes to Neo4j
    └── cost.py                     # CostTracker for tokens/dollars/calls

prompts/
├── _template.md                    # structural template for all prompts
├── planner.md
├── query_expander.md
├── extractor.md
├── validator.md
├── reflector.md
├── risk_analyzer.md
└── reporter.md

eval/
├── personas/
│   ├── persona_synthetic_a.yaml
│   ├── persona_synthetic_b.yaml
│   └── persona_real_public.yaml
├── plant_site/                     # GitHub Pages source for synthetic personas
├── runner.py
└── metrics.py

tests/
├── unit/
├── integration/
└── fixtures/                       # HTTP cassettes + recorded LLM responses

runs/                               # per-run output (gitignored except demo)
└── .gitkeep

streamlit_app.py                    # optional day-6 demo
```

**Structure Decision**: Single-project Python package (`src/research_agent/`) with separate top-level directories for prompts, eval, and tests. This is a CLI tool, not a web service — the package is invoked via `python -m research_agent run`. The `runs/` directory holds per-run output artifacts and is gitignored except for one demo run.

## Graph Wiring

```text
START ──► planner ──► search_orchestrator ──► extractor ──► validator ──► reflector
                                                                            │
                              ���──────── continue ◄──────────────────────────┤
                              │         (loop back to planner)              │
                              │                                             │
                              │         pivot ◄─────────────────────────────┤
                              │         (revised plan, back to planner)     │
                              │                                             │
                              ▼                                             │
                           planner                          terminate ◄─────┘
                                                               │
                                                               ▼
                                                         graph_builder ──► risk_analyzer ──► reporter ──► END
```

- **Checkpointer**: SqliteSaver at `runs/{run_id}/checkpoint.sqlite` for resume.
- **BudgetGuard**: Decorator on every node; updates `state.budget`; short-circuits to reflector on hard cap.
- **@traceable**: Every node decorated for LangSmith distributed tracing.
- **Conditional edges on reflector**: `continue` loops back with incremented iteration; `pivot` loops back with a revised plan; `terminate` exits the loop to graph_builder.

## Confidence Formula

```
confidence(claim) =
    0.35 × source_authority_max
  + 0.30 × normalized_log(independent_corroborations)
  + 0.15 × recency_factor
  + 0.20 × consistency_score
```

**Source tier mapping** (classified by GPT-5.4 Mini from URL + title):

| Tier | Score | Examples |
|------|-------|---------|
| 1 | 1.0 | SEC filings, gov sites, court records, regulatory filings |
| 2 | 0.8 | Major news outlets, official organization sites |
| 3 | 0.6 | Industry publications, professional bios, LinkedIn |
| 4 | 0.3 | Blogs, social media, forums |

- `independent_corroborations` = count of distinct registrable domains supporting the claim.
- `recency_factor` = 1.0 for timeless claims (education, birth); time-decayed for time-sensitive claims (current role, recent statements).
- `consistency_score` = 1.0 if no contradictions; penalty if contradicted by a claim with higher source authority.
- Weights are constants configurable via environment variables. The eval suite measures calibration and may trigger retuning.

## Risk Taxonomy

`RiskCategory` enum with 7 values:

| Category | Description | Examples |
|----------|-------------|---------|
| REGULATORY | Legal/regulatory exposure | Sanctions mentions, regulatory actions, lawsuits |
| REPUTATIONAL | Public reputation risk | Negative press, controversies, public disputes |
| NETWORK | Risky associations | Connections to flagged individuals/organizations |
| FINANCIAL | Financial irregularities | Unusual financial patterns, bankruptcy, debt |
| INCONSISTENCY | Contradictory information | Conflicting claims across sources |
| COVERAGE_GAP | Missing expected information | Unexplained employment gaps, missing public records |
| OTHER | Unclassified risk (requires justification) | Anything outside the above with non-empty `justification` |

**Severity scale** (per spec clarification): Low / Medium / High / Critical.

## Model Routing

| Role | Model | Rationale |
|------|-------|-----------|
| Planner, Reflector, Risk synthesis, Reporter | Claude Opus 4.7 | Long-horizon reasoning, nuanced synthesis, handles complex multi-step instructions |
| Extractor, Validator (cross-reference), Source tier classifier | GPT-5.4 Mini | Most reliable Pydantic structured output via function calling |
| Query expander, Snippet summarizer | Gemini 3 Flash | 10× cheaper for high-fanout loop work; adequate quality for expansion/summarization |

**Rejected alternative**: Single-model approach (all Claude Opus 4.7). Rejected because extraction/validation calls happen at high frequency (30-60× per run) and Claude Opus is 10× more expensive than Gemini Flash for the simpler tasks. Multi-model routing cuts cost by ~60% while maintaining quality where it matters.

## Search Routing

| Intent | Primary | Fallback |
|--------|---------|----------|
| Fresh news, biographical, professional | Brave Search | Tavily (env flag) |
| Semantic discovery ("similar to X", "connected to Y") | Exa | Brave Search |
| Full-page content extraction | Firecrawl | trafilatura on raw HTML via httpx |

**Cache**: SQLite-backed `SearchCache`. Key = `sha256(provider + ':' + normalized_query)`. TTL: 7 days for news intent, 30 days for biographical.
**Rate limiting**: tenacity with provider-specific rate budgets. Exponential backoff on 429/5xx.
**Robots.txt**: Checked by `fetch.py` before content extraction; disallowed URLs are dropped.

## Guardrails

Four chokepoints, four guardrails:

| Chokepoint | Guardrail | Implementation |
|------------|-----------|----------------|
| Target ingestion | `validate_input(target)` | Pydantic validation; name length cap (200 chars); character-class sanitization (no control chars); reject if all fields empty |
| Fetched web content | `wrap_untrusted_content(url, content)` | Wraps in `<source url="...">...</source>` XML delimiters; HTML-escapes content; model instructed to treat as data |
| LLM extraction output | `filter_pii(claim)` | Regex + heuristic PII detector; drops claims containing SSN/phone/email/address patterns; sensitive-attribute filter (health, religion, orientation) |
| Report persistence | `check_output_safety(text)` | Final scan for leaked PII; verifies scope-and-limitations section present; rejects if guardrail violations found |

## Memory Tiers

| Tier | Scope | Backing | Purpose |
|------|-------|---------|---------|
| Short-term | Within iteration | `ResearchState` fields | Current plan, current search results, current claims |
| Mid-term | Within run | LangGraph SqliteSaver checkpointer | Resume after crash; full state at each node boundary |
| Long-term | Across runs | SQLite (SearchCache) + Neo4j (EntityRegistry) | Avoid redundant searches; canonical entity dedup across investigations |

## Observability

Three layers, always on:

1. **LangSmith**: Every node decorated with `@traceable`. Project: `elile-research-agent`. Full prompt/response/token/cost metadata.
2. **Local audit log**: `runs/{run_id}/audit.json`. Per-node JSON entries with 8 axes: timestamp, node, input_state_hash, prompt_filled, raw_response, parsed_output, latency_ms, tokens (in/out), dollars, retries. Privileged engineer-only artifact (not PII-filtered).
3. **Cost tracker**: Updated by every LLM call and search call in `state.budget`. Visible at any node. Reported in final output.

## Testing Strategy

| Layer | Tool | Scope | When |
|-------|------|-------|------|
| Unit tests | pytest + respx | Mocked LLM (recorded responses), mocked HTTP | Every commit (`make test`) |
| Prompt schema tests | pytest | Verify each prompt's output validates against its Pydantic schema across 3 fixture inputs | Every commit |
| Integration tests | pytest --live | Real API calls to LLM/search providers | On demand (`make test-live`) |
| End-to-end fixture test | pytest | Full pipeline on recorded HTTP cassette | Every commit |
| Eval suite | eval/runner.py | 3 personas, recall/precision/calibration/risk-recall metrics | On demand (`make eval`), gated on prompt changes |

## Phasing

| Phase | Day | Deliverables |
|-------|-----|-------------|
| 0: Foundation | Day 1 AM | pyproject.toml, Makefile, .env.example, schemas.py, state.py, errors.py, guardrails.py, confidence.py, risk_taxonomy.py |
| 1: Tools | Day 1 PM | tools/llm.py, tools/search.py, tools/fetch.py, tools/neo4j_writer.py, tools/cost.py, memory.py, observability.py + unit tests |
| 2: Nodes + Graph | Day 2 | All 8 nodes, graph.py wiring, cli.py, all 7 prompts + prompt schema tests |
| 3: End-to-End | Day 3 | graph_builder, risk_analyzer, reporter nodes complete; first synthetic persona runs end-to-end; HTTP cassette fixture test |
| 4: Eval | Day 4 | eval/runner.py, eval/metrics.py, plant_site deploy, all 3 persona definitions, tuning pass on confidence weights |
| 5: Polish | Day 5 | Live target run, README with design decisions, ethical scope documentation, end-to-end demo recording prep |
| 6: Demo | Day 6 | Streamlit (if time), demo video recording, submission |

## Complexity Tracking

No constitution violations to justify. All gates pass.
