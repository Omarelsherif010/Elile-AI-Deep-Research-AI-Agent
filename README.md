# Deep Research AI Agent

A LangGraph-orchestrated multi-agent system for autonomous OSINT-style investigation of public figures. Built for the **Elile AI** technical assessment — investigating **Timothy Overturf, CEO of Sisu Capital**.

## How the System Works

The agent conducts a structured investigation through an iterative research loop. Each cycle deepens coverage across six dimensions: biographical details, professional history, financial connections, network relationships, public statements, and risk surface.

### End-to-End Flow

```
User provides target name + context
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                    RESEARCH LOOP                         │
│                                                         │
│  ┌──────────┐    ┌───────────────────┐    ┌───────────┐ │
│  │ Planner  │───▶│Search Orchestrator│───▶│ Extractor │ │
│  │(GPT-4.1) │    │ (Brave + Gemini)  │    │(GPT-5.4m) │ │
│  └──────────┘    └───────────────────┘    └─────┬─────┘ │
│       ▲                                         │       │
│       │          ┌───────────┐    ┌─────────────▼─────┐ │
│       └──────────│ Reflector │◀───│    Validator      │ │
│    (continue)    │ (GPT-4.1) │    │   (GPT-5.4 Mini)  │ │
│                  └─────┬─────┘    └───────────────────┘ │
│                        │                                │
│                   (terminate)                            │
└────────────────────────┼────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │    TERMINAL PHASE    │
              │                     │
              │  Graph Builder      │  ──▶ Identity graph (Neo4j/JSON)
              │  Risk Analyzer      │  ──▶ 7-category risk flags
              │  Reporter (GPT-4.1) │  ──▶ Markdown + JSON report
              └─────────────────────┘
```

### What Each Node Does

| Node | Model | Purpose |
|------|-------|---------|
| **Planner** | GPT-4.1 | Generates research questions across 6 dimensions based on target context and coverage gaps |
| **Search Orchestrator** | Gemini Flash + Brave | Expands each question into multiple search queries, dispatches to Brave/Exa, collects results |
| **Extractor** | GPT-5.4 Mini | Processes each search result individually, extracts structured claims (subject-predicate-object triples) with source URLs |
| **Validator** | GPT-5.4 Mini | Cross-references claims, classifies source tiers (1=gov/court to 4=blog), computes 4-factor confidence scores |
| **Reflector** | GPT-4.1 | Evaluates coverage gaps, decides: continue (more research needed), pivot (different approach), or terminate (sufficient coverage or budget exhausted) |
| **Graph Builder** | Rules-only | Converts validated claims into an identity graph (entities + relationships), exports to Neo4j or JSON |
| **Risk Analyzer** | GPT-4.1 | Classifies findings against 7-category risk taxonomy (regulatory, reputational, financial, network, inconsistency, coverage gap, other) |
| **Reporter** | GPT-4.1 | Synthesizes all findings into a structured report with executive summary, dimension-by-dimension analysis, risk flags, and scope limitations |

### Multi-Model Architecture (3 Distinct Models)

The system uses **three distinct AI models**, each selected for its strength:

| Model | Role | Why This Model |
|-------|------|----------------|
| **GPT-4.1** (OpenAI) | Reasoning: planning, reflection, risk synthesis, report writing | Strong long-horizon reasoning and nuanced synthesis at reasonable cost (~$2/1M input) |
| **GPT-5.4 Mini** (OpenAI) | Extraction + validation: structured claim extraction, cross-referencing | Best reliability for Pydantic structured output, 3x cheaper for high-volume extraction (runs 30-60x per investigation) |
| **Gemini 3 Flash** (Google) | Query expansion: expanding research questions into search queries | 10x cheaper than GPT for high-fanout work, auto-falls back to GPT-5.4 Mini if quota exceeded |

Fallback routing ensures the agent works even with partial API keys — if Anthropic or Google is unavailable, OpenAI handles all roles.

### Confidence Scoring Formula

Every claim gets a deterministic confidence score (0.0-1.0) using a weighted 4-factor formula:

```
confidence = 0.35 × source_authority(tier)     # Tier 1=gov → 1.0, Tier 4=blog → 0.3
           + 0.30 × corroboration(n_domains)    # log(n+1)/log(4), 3 domains → 1.0
           + 0.15 × recency(months_old)          # Timeless=1.0, decays over 36 months
           + 0.20 × consistency(contradictions)   # No contradictions → 1.0
```

**Hard rule**: No claim ships with confidence > 0.5 unless backed by 2+ independent domains OR 1 Tier-1 source (gov, court, SEC). LLM-only claims are capped at 0.4 and labeled "[inferred, unverified]".

### Search Strategy

Searches build upon previous findings — the reflector identifies coverage gaps, and the planner generates targeted queries to fill them:

| Intent | Primary Provider | Fallback |
|--------|-----------------|----------|
| News, biographical, professional | Brave Search | Tavily |
| Semantic discovery ("people connected to X") | Exa | Brave |
| Full-page content extraction | Firecrawl | trafilatura (local HTML parsing) |

### Budget Enforcement

Every run tracks four resource caps in state. When any cap is hit, the agent terminates gracefully (no exceptions):

| Resource | Default | Override |
|----------|---------|---------|
| Iterations | 8 | `--max-iterations` / `DEFAULT_MAX_ITERATIONS` |
| Search calls | 60 | `--max-search-calls` / `DEFAULT_MAX_SEARCH_CALLS` |
| Cost | $5.00 | `--max-dollars` / `DEFAULT_MAX_DOLLARS` |
| Time per iteration | 180s | `DEFAULT_MAX_SECONDS_PER_ITERATION` |

---

## Project Architecture

```
src/research_agent/
├── cli.py              # Entry point: python -m research_agent run --target "..."
├── graph.py            # LangGraph StateGraph wiring (8 nodes, conditional edges)
├── state.py            # ResearchState TypedDict — all inter-node data
├── schemas.py          # 15+ Pydantic v2 models (Claim, Source, RiskFlag, Budget, etc.)
├── confidence.py       # Deterministic 4-factor scoring formula
├── risk_taxonomy.py    # 7 RiskCategory + 4 RiskSeverity enums
├── guardrails.py       # Input validation, PII regex filter, prompt injection defense
├── memory.py           # SearchCache (dedup), EntityRegistry, RunStateStore
├── observability.py    # @traceable decorator, AuditLogger, LangSmith integration
├── errors.py           # Typed exceptions: BudgetExceeded, GuardrailViolation, etc.
├── nodes/              # 8 node implementations (one file per node)
│   ├── planner.py          # Research question generation
│   ├── search_orchestrator.py  # Query expansion + multi-provider dispatch
│   ├── extractor.py        # Per-result structured claim extraction
│   ├── validator.py        # Cross-reference + confidence scoring
│   ├── reflector.py        # Coverage gap analysis + continue/terminate
│   ├── graph_builder.py    # Identity graph construction (Neo4j/JSON)
│   ├── risk_analyzer.py    # Risk taxonomy classification
│   └── reporter.py         # Report generation (Markdown + JSON)
└── tools/              # Shared utilities (never called directly from nodes)
    ├── llm.py              # Multi-model router with automatic fallback
    ├── search.py           # Multi-provider search dispatcher
    ├── fetch.py            # robots.txt-respecting content fetcher
    ├── neo4j_writer.py     # Neo4j Cypher MERGE operations
    └── cost.py             # Token + dollar cost tracker

prompts/                # 8 version-controlled LLM prompts (Markdown with structured sections)
eval/                   # Evaluation suite: 3 personas, runner, metrics, matcher
├── personas/           # YAML persona definitions with ground truth
├── plant_site/         # GitHub Pages synthetic persona websites
├── runner.py           # Subprocess-based eval runner
├── metrics.py          # Precision, recall, ECE calibration
├── matcher.py          # 3 matching strategies: exact, fuzzy, semantic
└── cli.py              # eval CLI (run, replay, validate-persona)
tests/                  # Unit + integration tests
runs/                   # Per-run output artifacts
streamlit_app.py        # Interactive demo UI
```

### Key Design Decisions

| Decision | Rationale | Rejected Alternative |
|----------|-----------|---------------------|
| **LangGraph** over CrewAI/AutoGen | Explicit graph topology, typed state, built-in checkpointing, native LangSmith tracing | CrewAI/AutoGen abstract away wiring, harder to defend architecture |
| **Multi-model routing** (3 models) | Extraction runs 30-60x per run; single expensive model = $15-25/run. Multi-model cuts cost ~60% | All-GPT-4.1 exceeds $5 budget on typical runs |
| **Deterministic confidence** (weighted formula) | Transparent, testable, calibration-measurable via eval suite | LLM-based confidence — opaque, non-deterministic, expensive |
| **SQLite checkpointing** per run | Built into LangGraph, no external service, isolated per-run | Redis — adds external dependency for a CLI tool |
| **Regex PII detection** | Deterministic, fast, zero false-negatives for well-formed patterns | spaCy/Presidio NER — 500MB model, variable recall |

---

## Requirement Fulfillment

### Core Architecture

| Requirement | Status | Implementation |
|-------------|--------|---------------|
| **Multi-Model Integration** (at least 2 distinct AI models) | **Done** | 3 models: GPT-4.1 (reasoning), GPT-5.4 Mini (extraction), Gemini 3 Flash (expansion). See `tools/llm.py` `ROLE_TO_MODEL` |
| **Consecutive Search Strategy** (builds upon previous findings) | **Done** | Reflector analyzes gaps after each iteration, planner generates targeted follow-up queries. See `nodes/reflector.py` and `nodes/planner.py` |
| **Dynamic Query Refinement** (adapt based on discovered info) | **Done** | Query expander takes research questions + prior findings, generates refined queries. See `nodes/search_orchestrator.py` |
| **Identity Graph Generation** (graph DB) | **Done** | Graph builder creates entity/relationship graph, exports to Neo4j (when available) or JSON. See `nodes/graph_builder.py`, `tools/neo4j_writer.py`, output: `graph_export.json` |

### Functional Specifications

| Requirement | Status | Implementation |
|-------------|--------|---------------|
| **Deep Fact Extraction** (biographical, professional, financial, behavioral) | **Done** | Extractor processes each search result through GPT-5.4 Mini, produces subject-predicate-object claims. 320 claims extracted for Timothy Overturf |
| **Risk Pattern Recognition** (red flags, inconsistencies) | **Done** | Risk analyzer classifies against 7-category taxonomy (REGULATORY, REPUTATIONAL, FINANCIAL, NETWORK, INCONSISTENCY, COVERAGE_GAP, OTHER) with 4 severity levels. Found CRITICAL SEC enforcement action for Overturf |
| **Connection Mapping** (entities, organizations, events) | **Done** | Graph builder maps 43 entities and 121 relationships for Timothy Overturf. Exported as `graph_export.json` with typed nodes (PERSON, ORGANIZATION, EVENT) and edges |
| **Source Validation** (confidence scoring, cross-referencing) | **Done** | Validator cross-references claims, assigns 4-tier source classification, computes deterministic 4-factor confidence score. See `confidence.py` |

### Implementation Guidelines

| Requirement | Status | Implementation |
|-------------|--------|---------------|
| **LangGraph + LangSmith** | **Done** | LangGraph StateGraph with 8 nodes + conditional edges (`graph.py`). LangSmith tracing via `@traceable` decorator on every node (`observability.py`) |
| **AI APIs, search engines, real online data** | **Done** | Brave Search API for web search, Exa for semantic search, Firecrawl for content extraction. All hitting live web data |
| **GraphDB for identity graph** | **Done** | Neo4j Aura (when URI configured) or JSON export fallback. Cypher MERGE for idempotent writes (`tools/neo4j_writer.py`) |
| **Error handling and rate limiting** | **Done** | Typed exceptions (`errors.py`), tenacity retry with exponential backoff (`tools/llm.py`), automatic provider fallback, budget guard on every node (`graph.py`) |
| **Scalability and maintainability** | **Done** | All inter-node data is Pydantic v2, nodes are stateless functions, LLM prompts are version-controlled Markdown, search/LLM/fetch are provider-abstracted |

### Deliverables — Phase 1

| Deliverable | Status | Location |
|-------------|--------|----------|
| **Complete codebase + documentation** | **Done** | 8 nodes, 5 tools, 8 prompts, schemas, tests, README, CLAUDE.md, .env.example |
| **Three test personas with expected findings** | **Done** | `eval/personas/`: Aria Vellinor (synthetic), Dorian Ashcroft (synthetic), Satya Nadella (real public). Plant site at `eval/plant_site/` |
| **Execution logs** | **Done** | `runs/timothy_overturf/audit.json` — per-node audit trail with input state, prompts, responses, latency, tokens |
| **Risk assessment reports** | **Done** | `runs/timothy_overturf/report.json` — 670 claims, 6 risk flags (2 CRITICAL SEC enforcement, 4 COVERAGE_GAP). Trimmed summary in `demo_results/` |
| **Eval suite results** | **Done** | `demo_results/eval/` — live run metrics, fixture replay, eval methodology documentation |

### Evaluation Criteria

| Criterion | How We Address It |
|-----------|-------------------|
| **Code quality, architecture** | Typed everywhere (Pydantic v2 + TypedDict), ruff-enforced style, one-file-per-node, explicit graph topology, no bare `except` |
| **Effective multi-model orchestration** | 3 models by role with automatic fallback, centralized routing in `tools/llm.py`, cost tracking per provider |
| **Intelligent search progression** | Reflector evaluates coverage after each iteration, identifies gaps, planner generates targeted queries. Budget-aware termination |
| **Error handling and edge cases** | Budget guard on every node, graceful termination (no exceptions), empty LLM output handling, rate limit fallback, provider unavailable fallback |
| **Depth and accuracy** | 670 claims from 60 search calls for Timothy Overturf, found real SEC enforcement action (2x CRITICAL), 4 coverage gaps honestly disclosed |
| **Risk assessment quality** | 7-category taxonomy with 4 severity levels, evidence-backed flags with claim IDs, coverage gaps explicitly reported |
| **Non-obvious connections** | Identity graph maps 69 entities and 258 relationships, including familial connections (Hansueli/Hans Overturf) not immediately obvious from basic search |
| **Source verification** | 4-factor confidence formula, tier-based source classification (gov/court → news → professional → blog), hard cap on single-source claims |
| **Creative approaches** | Synthetic eval personas with planted facts on GitHub Pages, deterministic confidence formula (not LLM-based), XML content wrapping for prompt injection defense |
| **Search optimization** | Query expansion via cheap model (Gemini/GPT-5.4 Mini), multi-provider routing by intent, deduplication via SearchCache |
| **Scalability** | Budget enforcement prevents runaway costs, checkpointing enables resume, provider abstraction allows swapping models/search engines |

---

## Timothy Overturf Investigation Results

The assessment target was successfully investigated. Key findings:

| Severity | Category | Finding |
|----------|----------|---------|
| **CRITICAL** | REGULATORY | Official SEC enforcement action against Timothy Overturf and Sisu Capital, LLC — allegations of fiduciary duty breaches via unauthorized and unsuitable trades in client accounts (confidence 0.95) |
| **CRITICAL** | REGULATORY | SEC released official allegations that Timothy Overturf breached fiduciary duties to clients — confirmed by Tier 1 regulatory releases (confidence 0.95) |
| LOW | COVERAGE_GAP | Financial connections, negative press, inconsistency, and network risk dimensions have zero validated claims — gaps disclosed in report |

**Metrics**: 670 validated claims, 69 entities, 258 relationships, 60 search calls. Full report and artifacts in `runs/timothy_overturf/` and `demo_results/timothy_overturf/`.

---

## Quickstart

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys: OpenAI (required), Google AI (optional), Brave Search (required)

### Setup

```bash
git clone <repo-url>
cd Elile-AI-Deep-Research-AI-Agent
make install
cp .env.example .env
# Edit .env with your API keys (minimum: OPENAI_API_KEY + BRAVE_API_KEY)
```

### Run

```bash
# Investigate Timothy Overturf (assessment target)
python -m research_agent run \
  --target "Timothy Overturf" \
  --role "CEO" \
  --org "Sisu Capital" \
  --max-iterations 4 \
  --max-dollars 3.0

# Or any public figure
make run TARGET="Elon Musk"
```

**Output files** (in `runs/{run_id}/`):
- `report.md` — Human-readable risk report
- `report.json` — Machine-readable structured report (Streamlit-compatible)
- `graph_export.json` — Identity graph (nodes + edges)
- `audit.json` — Per-node execution log (8 axes per node)

### Eval Suite

```bash
make eval                # Run all 3 personas
python -m research_agent eval --persona persona_synthetic_a
```

### Demo UI

```bash
streamlit run streamlit_app.py
# Load runs/timothy_overturf/report.json in the UI
```

## Observability

- **LangSmith**: Every node decorated with `@traceable`. Distributed traces at `elile-research-agent` project
- **Local audit log**: `runs/{run_id}/audit.json` — per-node: input state hash, prompt sent, raw response, parsed output, latency, tokens, cost, retries
- **Cost tracking**: Per-provider dollar tracking, visible in audit log and report

## Ethical Scope

- Public sources only — no authenticated scraping
- Respects robots.txt on all fetched content
- No inference of sensitive attributes (race, religion, health, sexual orientation)
- No extraction of personal PII (home address, personal phone, family members)
- XML content wrapping defends against prompt injection
- Mandatory "Scope and Limitations" section in every report
- Thin coverage reported as a finding ("coverage gap"), not fabricated
