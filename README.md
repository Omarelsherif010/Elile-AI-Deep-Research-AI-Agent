# Deep Research Agent

A LangGraph-orchestrated multi-agent system for OSINT-style investigation of public figures.

## What It Does

Given a target person's name, the agent:
1. Generates an iterative research plan across 6 dimensions (biographical, professional, financial, network, public statements, risk surface)
2. Expands and dispatches search queries to Brave Search, Exa, and Firecrawl
3. Extracts structured claims with source provenance via GPT-4.1
4. Cross-validates claims, classifies source tiers, and computes a 4-factor confidence score
5. Reflects on coverage gaps and decides to continue, pivot, or terminate
6. Builds an identity graph (Neo4j or JSON export)
7. Analyzes risk patterns against a 7-category taxonomy
8. Produces an auditable Markdown + JSON risk report

## Architecture

```
START → planner → search_orchestrator → extractor → validator → reflector
                                                                    │
                        ┌── continue/pivot (loop) ←────────────────┘
                        │
                        └── terminate → graph_builder → risk_analyzer → reporter → END
```

### Model Routing

| Role | Model | Rationale |
|------|-------|-----------|
| Planner, Reflector, Risk synthesis, Reporter | Claude Opus 4 | Long-horizon reasoning |
| Extractor, Validator | GPT-4.1 | Most reliable structured output |
| Query expander | Gemini 2.5 Flash | 10× cheaper for high-fanout loop |

### Search Routing

| Intent | Primary | Fallback |
|--------|---------|----------|
| News, biographical, professional | Brave Search | Tavily |
| Semantic discovery | Exa | Brave |
| Full-page extraction | Firecrawl | trafilatura |

## Design Decisions

### 1. LangGraph over CrewAI/AutoGen
**Decision**: LangGraph with hand-built StateGraph.
**Rationale**: Explicit graph topology, typed state, built-in checkpointing (SqliteSaver), native LangSmith tracing.
**Rejected**: CrewAI/AutoGen — abstract away the wiring, making it harder to defend architectural choices.

### 2. Multi-model routing
**Decision**: Three models by role.
**Rationale**: Extraction runs 30-60× per run; Opus at full price = ~$15-25/run. Multi-model cuts cost ~60%.
**Rejected**: All-Opus — exceeds $5 budget cap on typical runs.

### 3. Deterministic confidence formula
**Decision**: Weighted 4-factor formula (source authority × 0.35 + corroboration × 0.30 + recency × 0.15 + consistency × 0.20).
**Rationale**: Transparent, testable, calibration-measurable via eval suite.
**Rejected**: LLM-based confidence — opaque, non-deterministic, expensive to calibrate.

### 4. SQLite checkpointing
**Decision**: LangGraph SqliteSaver per run.
**Rationale**: Built-in to LangGraph, no external service, isolated per-run files.
**Rejected**: Redis — adds external dependency for a single-user CLI.

### 5. Regex PII detection
**Decision**: Regex + heuristic keyword filter.
**Rationale**: Deterministic, fast, zero false-negatives for well-formed PII patterns.
**Rejected**: spaCy/Presidio NER — 500MB model, variable recall, overkill for v1.

## Ethical Scope

This system operates exclusively on **public sources**. It:
- Respects robots.txt on all fetched content
- Does not infer sensitive attributes (race, religion, health, sexual orientation)
- Does not extract personal PII (home address, personal phone, family member names)
- Wraps all fetched content in XML delimiters to defend against prompt injection
- Includes a mandatory "Scope and Limitations" section in every report
- Reports thin coverage as a finding ("coverage gap"), not a failure

## Quickstart

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys: Anthropic (Claude), OpenAI (GPT-4.1), Google AI (Gemini), Brave Search

### Setup

```bash
git clone <repo-url>
cd deep-research-agent
make install
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
make run TARGET="Elon Musk"
# or with more context:
python -m research_agent run \
  --target "Jane Smith" \
  --role "CEO" \
  --org "Acme Corp" \
  --output runs/jane-smith
```

**Output files** (in `--output` directory):
- `report.md` — Human-readable risk report
- `report.json` — Machine-readable structured report
- `graph_export.json` — Identity graph (nodes + edges)
- `audit.json` — Per-node execution log (engineer-only)
- `checkpoint.sqlite` — Resumable LangGraph checkpoint

### Eval Suite

```bash
make eval                                        # all 3 personas
python -m research_agent eval --persona persona_synthetic_a
```

## Project Structure

```
src/research_agent/
├── schemas.py          # All Pydantic v2 models
├── state.py            # ResearchState TypedDict
├── graph.py            # LangGraph wiring
├── confidence.py       # 4-factor scoring formula
├── risk_taxonomy.py    # RiskCategory + RiskSeverity enums
├── guardrails.py       # Input/output validation, PII filter
├── memory.py           # SearchCache, EntityRegistry, RunStateStore
├── observability.py    # AuditLogger + LangSmith + CostTracker
├── errors.py           # Typed exceptions
├── cli.py              # argparse entry point
├── nodes/              # 8 LangGraph nodes
└── tools/              # LLM, search, fetch, Neo4j, cost

prompts/                # Runtime LLM prompts (version-controlled Markdown)
eval/                   # Eval personas, plant_site, metrics, runner
tests/                  # Unit + integration tests
runs/                   # Per-run output artifacts (gitignored)
```

## Commands

```bash
make install        # Install dependencies via uv
make lint           # Ruff check + format check
make test           # Unit tests (mocked, fast)
make test-live      # Integration tests (real APIs)
make run TARGET="X" # Run against a target
make eval           # Run eval suite
make demo           # Streamlit demo (optional)
make clean          # Remove build artifacts
```

## Budget Defaults

| Cap | Default | Override |
|-----|---------|---------|
| Iterations | 8 | `--max-iterations` |
| Search calls | 60 | `--max-search-calls` |
| Cost | $5.00 | `--max-dollars` |

## Observability

- **LangSmith**: Every node decorated with `@traceable`. Set `LANGSMITH_API_KEY` to enable.
- **Local audit log**: `runs/{run_id}/audit.json` — JSONL with 8 axes per node execution.
- **Cost tracking**: Updated at every LLM/search call; visible in report and audit log.

## Environment Variables

See `.env.example` for the full list. Required: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `BRAVE_API_KEY`.

## Assessment Context

Built as a 5–6 day technical assessment for **Elile AI** (Dubai). Evaluation surfaces:
- Architectural defensibility (every choice documented with rationale + rejected alternative)
- Production sensibility (budget enforcement, observability, evals, ethical scope)
