# Deep Research Agent — Claude Code Context

This file is loaded by Claude Code on every session. It is the project's single source of truth for stack, conventions, and constraints. Read it first; act on it always.

---

## What this project is

A LangGraph-orchestrated multi-agent system that conducts OSINT-style investigation of public figures. Given a target person, it iteratively searches the web, extracts structured claims with provenance, validates them with confidence scoring, surfaces risk patterns from a typed taxonomy, builds an identity graph in Neo4j, and produces an auditable risk report.

This is a 5–6 day technical assessment for **Elile AI** (Dubai). They build agentic AI for mission-critical infrastructure. Two evaluation surfaces matter most: **architectural defensibility** (every choice has a written rationale) and **production sensibility** (budgets, evals, observability, ethical scope are first-class).

The deliverable is a public GitHub repo + an 8–12 minute demo video. Graders will read the code, run the eval suite, and inspect prompts.

---

## Operating principles (the constitution)

These are non-negotiable. They override convenience.

1. **Ethical scope is the first thing checked.** Public sources only. Robots.txt respected. No PII synthesis. No scraping behind authentication. No inference of sensitive attributes (race, religion, health, sexual orientation). Every report includes a "scope and limitations" section.

2. **Every claim is provenanced.** No claim about a person is stored without ≥1 source URL. No claim ships with confidence > 0.5 unless backed by ≥2 independent domains OR 1 Tier-1 source (gov, court, SEC). LLM-only-derived claims are tagged as such with confidence ≤ 0.4.

3. **Prompts are code.** All runtime LLM prompts live in `prompts/*.md` with structured sections (Role, Context, Task, Output Format, Constraints, Examples, Notes). They are version-controlled and reviewed.

4. **Budgets are enforced in state, not in code paths.** Every run tracks tokens, dollars, and step count in `ResearchState`. Hard caps trigger graceful termination, not exceptions.

5. **Evals drive confidence.** Three eval personas with planted ground truth. Recall, precision, and confidence calibration measured per release. No prompt or weight change ships without re-running evals.

6. **Observability is first-class.** LangSmith for distributed traces, local audit JSON for offline review, cost tracking in state. Eight per-node axes: input state hash, prompt sent, raw response, parsed output, latency, tokens, cost, retries.

7. **Types over strings.** All inter-node data is Pydantic v2. LLMs do classification, extraction, synthesis. Rules do routing, scoring, graph writes.

8. **We build what we can defend in 8 minutes.** Every architectural choice has a written rationale and one rejected alternative. If we can't justify it under live questioning, we cut it.

9. **Guardrails are layered.** Input sanitization, prompt-injection defense via content delimiting, output schema validation, PII filtering before persistence. Tools are MCP-shaped (auditable, retriable, sandboxed).

10. **No fabrication.** When public coverage is thin, the agent reports thin coverage. "Coverage gap" is a finding, not a failure.

---

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | LangGraph requires modern Python |
| Package manager | `uv` | 10× faster than pip; current standard |
| Lint/format | `ruff` | Replaces black, isort, flake8 |
| Tests | `pytest` | With `pytest-asyncio` for async tools |
| Schemas | Pydantic v2 | Required for OpenAI structured outputs |
| Orchestration | LangGraph ≥ 1.1 | Hand-built graph; not `deepagents` |
| Tracing | LangSmith | Project: `elile-research-agent` |
| LLM SDKs | `anthropic`, `openai`, `google-generativeai` | One per role |
| Search | `brave-search-python-client`, `exa-py`, `firecrawl-py` | Provider-abstracted |
| Graph DB | Neo4j (Aura free tier) | Cypher writes; idempotent MERGE |
| Demo UI | Streamlit (optional, day 6) | If time allows |

### Model routing

Use `tools/llm.py` to route by role. Never hardcode a provider in a node.

| Role | Model | Why |
|---|---|---|
| Planner / Reflector / Risk synthesis / Reporter | Claude Opus 4.7 | Long-horizon reasoning, nuanced synthesis |
| Extractor / Validator (cross-ref) | GPT-5.4 Mini | Most reliable Pydantic structured output |
| Query expander / Snippet summarizer | Gemini 3 Flash | 10× cheaper for high-fanout loop work |

### Search routing

Use `tools/search.py` to route by intent. Never call providers directly from nodes.

| Intent | Primary | Fallback |
|---|---|---|
| Fresh news, biographical, professional | Brave | Tavily (env flag) |
| Semantic discovery ("similar to X", "people connected to Y") | Exa | Brave |
| Full-page content extraction | Firecrawl | `trafilatura` on raw HTML |

---

## Directory layout

```
deep-research-agent/
├── CLAUDE.md                      # this file
├── README.md
├── Makefile
├── pyproject.toml
├── .env.example
├── .specify/                      # spec-kit artifacts (do not hand-edit)
│   └── memory/
│       └── constitution.md
├── specs/                         # spec-kit specs (one per feature)
│   └── 001-deep-research-agent/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
├── .claude/
│   └── commands/                  # custom Claude Code slash commands
├── prompts/                       # runtime LLM prompts (not Claude Code)
│   ├── _template.md
│   ├── planner.md
│   ├── query_expander.md
│   ├── extractor.md
│   ├── validator.md
│   ├── reflector.md
│   ├── risk_analyzer.md
│   └── reporter.md
├── src/research_agent/
│   ├── __init__.py
│   ├── cli.py                     # python -m research_agent run --target "..."
│   ├── schemas.py                 # all pydantic models
│   ├── state.py                   # ResearchState TypedDict
│   ├── graph.py                   # LangGraph wiring
│   ├── confidence.py              # scoring formula
│   ├── risk_taxonomy.py
│   ├── guardrails.py              # input/output validation, PII, injection defense
│   ├── memory.py                  # SearchCache, EntityRegistry, RunStateStore
│   ├── observability.py           # LangSmith + audit log
│   ├── nodes/
│   │   ├── planner.py
│   │   ├── search_orchestrator.py
│   │   ├── extractor.py
│   │   ├── validator.py
│   │   ├── reflector.py
│   │   ├── graph_builder.py
│   │   ├── risk_analyzer.py
│   │   └── reporter.py
│   └── tools/
│       ├── search.py
│       ├── fetch.py
│       ├── llm.py
│       ├── neo4j_writer.py
│       └── cost.py
├── eval/
│   ├── personas/
│   ├── plant_site/                # GitHub Pages source for synthetic personas
│   ├── runner.py
│   └── metrics.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                  # HTTP cassettes
└── runs/                          # per-run output (gitignored except a demo run)
```

---

## Conventions

### Code style
- Ruff defaults; line length 100.
- Type hints everywhere. `from __future__ import annotations` at the top of every file.
- No bare `except`. Catch specific exceptions; log; re-raise or convert to a typed error.
- All public functions have docstrings. Private helpers (`_foo`) don't need one.
- Imports in order: stdlib, third-party, local. Ruff's `I` rule enforces this.

### Naming
- Modules: `snake_case`.
- Classes: `PascalCase`. Pydantic models end in their nature: `Claim`, `ValidatedClaim`, `RiskFlag`, not `ClaimModel`.
- Functions: `snake_case`, verb-first (`extract_claims`, `validate_source`).
- Constants: `UPPER_SNAKE`. Live at module top.

### Errors
- Define typed errors in `src/research_agent/errors.py`: `BudgetExceeded`, `GuardrailViolation`, `ProviderUnavailable`, `SchemaValidationError`.
- Nodes never raise on recoverable conditions — they update state and signal the reflector.

### Tests
- Unit tests mock LLM and HTTP. Use `respx` for HTTP, fixture responses for LLM.
- Integration tests run against real LLM with a `--live` flag; default skipped.
- Eval suite lives in `eval/`, not `tests/`. Different cadence, different purpose.

### Git
- One logical change per commit.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- Branch per spec phase; PR-style review even if solo (forces a diff read).

---

## Behavior expectations for Claude Code

When working on this project:

1. **Read the spec first.** Before implementing any task, open the relevant `specs/001-deep-research-agent/spec.md` section. Don't infer requirements from task descriptions alone.

2. **Respect the constitution.** If a request conflicts with the constitution, surface the conflict before acting. Example: "This task implies hardcoding a provider in the node, which violates principle 7 (model routing centralized in `tools/llm.py`). Confirm the deviation or refactor?"

3. **Never invent file paths.** If a referenced file doesn't exist, ask. Don't create scaffolding silently.

4. **Pydantic everywhere.** Any function that takes or returns LLM output uses a Pydantic model. No untyped dicts crossing module boundaries.

5. **Tests with the code.** When implementing a node or tool, write its unit test in the same change. No "I'll add tests later."

6. **Cost-aware.** When generating prompts or graph logic, prefer fewer LLM calls and shorter contexts. If a task description implies a wasteful pattern, suggest the cheaper alternative.

7. **No new dependencies without justification.** If a task seems to need a new package, propose it in chat first with a one-line rationale. Default to the standard library.

8. **Surface trade-offs.** When there are multiple reasonable approaches, list 2–3 with one-line pros/cons before committing. The decision belongs to the human.

9. **Don't touch `.specify/` directly.** That directory is owned by Spec-Kit. To change a spec, run `/speckit.specify` again or edit through the workflow.

10. **Stop at acceptance criteria.** When a task says "implement node X," do exactly that and the test. Don't expand into adjacent nodes uninvited.

---

## Common commands

```bash
make install        # uv sync
make lint           # ruff check + ruff format --check
make test           # pytest (mocked)
make test-live      # pytest --live (real APIs, slow)
make run TARGET="Jane Doe"
make eval           # run all 3 personas, emit metrics
make demo           # streamlit run streamlit_app.py
make clean
```

---

## Things explicitly out of scope

These will come up in conversation. Decline politely and link the rationale.

- A general-purpose web crawler (we use search APIs).
- A vector database / RAG layer (live retrieval only; the corpus is the open web).
- Authentication, multi-tenant deployment, CI/CD pipelines.
- A web frontend beyond Streamlit.
- Translating non-English sources (flagged but not extracted in v1).
- Inference of any sensitive attribute (race, religion, health, orientation, etc.).
- Sanctions list / OFAC integration (production consideration; not v1).
- Human-in-the-loop approval gates (v1 is fully autonomous within budget).

---

## Pointers

- **Spec-Kit reference:** [github.com/github/spec-kit](https://github.com/github/spec-kit)
- **Anthropic prompt engineering:** [docs.anthropic.com/en/docs/build-with-claude/prompt-engineering](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview) — the brief explicitly linked this. Mirror these patterns in `prompts/*.md`.
- **LangGraph docs:** [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/)
- **MCP design tenets:** [modelcontextprotocol.io](https://modelcontextprotocol.io) — we don't use MCP servers but our tools are MCP-shaped.

## Active Technologies
- Python 3.11+ + LangGraph ≥1.1, Pydantic v2, anthropic SDK, openai SDK, google-generativeai SDK, neo4j Python driver, httpx, tenacity, structlog, trafilatura (001-deep-research-agent)
- Neo4j Aura free tier (graph, optional); SQLite (search cache, checkpoints); filesystem (runs/, audit logs) (001-deep-research-agent)
- Python 3.11+ + pydantic >=2.0 (schemas), pyyaml (persona loading), rapidfuzz (fuzzy matching), openai >=1.50 (embeddings via text-embedding-3-small), jinja2 (report templates), structlog (logging) (002-eval-suite)
- Filesystem (YAML personas, JSON artifacts, Markdown reports, JSON match cache) (002-eval-suite)

## Recent Changes
- 001-deep-research-agent: Added Python 3.11+ + LangGraph ≥1.1, Pydantic v2, anthropic SDK, openai SDK, google-generativeai SDK, neo4j Python driver, httpx, tenacity, structlog, trafilatura
