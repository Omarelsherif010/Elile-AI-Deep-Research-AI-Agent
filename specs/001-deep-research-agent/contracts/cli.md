# CLI Contract

**Module**: `src/research_agent/cli.py`
**Entry point**: `python -m research_agent run`

## Commands

### `run` — Execute a research investigation

```
python -m research_agent run \
  --target "Name"            \   # required: target person's name
  [--aliases "Alias1,Alias2"] \  # comma-separated alternate names
  [--role "CEO"]              \  # target's role/title
  [--org "Acme Corp"]         \  # target's organization
  [--context "Additional..."]  \ # freeform context
  [--geo "Dubai, UAE"]         \ # geographic hint
  [--output runs/<id>]         \ # output directory (default: runs/<uuid>)
  [--max-iterations 8]         \ # override budget cap
  [--max-search-calls 60]      \ # override budget cap
  [--max-dollars 5.0]           # override budget cap
```

**Exit codes**:
- 0: Success — all outputs produced
- 1: Input validation failure (malformed target)
- 2: Budget exhausted (outputs still produced with partial results)
- 3: All search providers failed (coverage-gap report produced)
- 4: Unrecoverable error (config missing, API keys invalid)

**Outputs** (written to `--output` directory):
- `report.md` — Human-readable Markdown risk report
- `report.json` — Structured JSON report (same data, machine-readable)
- `graph_export.json` — Identity graph as JSON (nodes + edges)
- `audit.json` — Per-node audit log (JSONL, engineer-only)
- `checkpoint.sqlite` — LangGraph checkpointer state (for resume)

### `eval` — Run evaluation suite

```
python -m research_agent eval \
  [--persona persona_synthetic_a]  \ # specific persona (default: all)
  [--output eval/results/<date>]     # results directory
```

## Environment Variables

Required (in `.env`):
- `ANTHROPIC_API_KEY` — Claude Opus 4 access
- `OPENAI_API_KEY` — GPT-4.1 access
- `GOOGLE_API_KEY` — Gemini 2.5 Flash access
- `BRAVE_API_KEY` — Brave Search access

Optional:
- `EXA_API_KEY` — Exa semantic search (degrades to Brave if missing)
- `FIRECRAWL_API_KEY` — Firecrawl extraction (degrades to trafilatura if missing)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Neo4j Aura (graph DB write skipped if missing)
- `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` — LangSmith tracing (local audit log still written if missing)
- `TAVILY_API_KEY` — Tavily as Brave fallback
- `CONFIDENCE_WEIGHT_*` — Override confidence formula weights (e.g., `CONFIDENCE_WEIGHT_AUTHORITY=0.35`)
