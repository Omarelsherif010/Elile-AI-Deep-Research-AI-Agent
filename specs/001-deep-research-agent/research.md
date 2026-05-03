# Research: Deep Research AI Agent

**Phase**: 0 (Outline & Research)
**Date**: 2026-05-03

All NEEDS CLARIFICATION items from the Technical Context have been resolved. This document records technology decisions with rationale and rejected alternatives.

## Decision 1: Orchestration Framework

**Decision**: LangGraph ≥1.1 with hand-built StateGraph.
**Rationale**: LangGraph provides typed state management, conditional edges, checkpointing (SqliteSaver), and native LangSmith tracing. It is the only framework that supports all four: typed state, conditional branching, resume from checkpoint, and distributed tracing without custom wiring.
**Rejected alternative**: CrewAI / AutoGen. Rejected because they abstract away the graph topology, making it harder to defend architectural choices under live questioning (Principle 8). LangGraph keeps the wiring explicit and inspectable.

## Decision 2: Multi-Model Routing

**Decision**: Three models routed by role — Claude Opus 4 (reasoning), GPT-4.1 (extraction), Gemini 2.5 Flash (expansion).
**Rationale**: Different tasks have different cost/quality profiles. Planning and synthesis require deep reasoning (Opus). Extraction/validation requires the most reliable structured output (GPT-4.1). Query expansion is high-fanout and low-complexity (Flash at 10× lower cost).
**Rejected alternative**: Single-model (all Opus). Rejected because a typical run makes 30-60 extraction calls. At Opus pricing, a single run would cost ~$15-25, exceeding the $5 budget cap. Multi-model routing cuts cost by ~60%.

## Decision 3: Search Provider Stack

**Decision**: Brave (primary web search), Exa (semantic discovery), Firecrawl (content extraction), trafilatura (fallback extraction).
**Rationale**: Brave provides fresh web results with a generous free tier. Exa enables semantic queries ("people connected to X") that keyword search cannot. Firecrawl handles JavaScript-rendered pages. trafilatura is a zero-cost fallback for static HTML.
**Rejected alternative**: Tavily as primary. Rejected because Brave's free tier is more generous (1000 req/month vs 100) and Tavily's semantic features overlap with Exa. Tavily retained as an env-flag fallback for Brave.

## Decision 4: Graph Database

**Decision**: Neo4j Aura free tier for live graph; JSON export as primary always-produced artifact.
**Rationale**: Neo4j provides native graph querying (Cypher) for analyst exploration. Aura free tier costs nothing. The in-memory graph + JSON export is always produced regardless of Neo4j availability (per spec clarification), so the system degrades gracefully.
**Rejected alternative**: NetworkX only (no external DB). Rejected because analysts need to query the graph interactively across runs, which requires a persistent store. NetworkX is in-process only.

## Decision 5: Confidence Scoring Approach

**Decision**: Deterministic weighted formula with 4 factors (source authority, corroboration count, recency, consistency).
**Rationale**: A rule-based formula is transparent, testable, and explainable — each factor's contribution is visible in the report (Principle 2). The eval suite measures calibration, allowing weight tuning.
**Rejected alternative**: LLM-based confidence scoring. Rejected because LLM scores are opaque, non-deterministic, and expensive to calibrate. A rule-based formula satisfies Principle 7 (prefer rules over LLM calls).

## Decision 6: Checkpointing Strategy

**Decision**: LangGraph SqliteSaver at `runs/{run_id}/checkpoint.sqlite`.
**Rationale**: SqliteSaver is built into LangGraph, requires no external service, and supports resume from any node boundary. Each run gets its own SQLite file, so runs are isolated and portable.
**Rejected alternative**: Redis-backed checkpointer. Rejected because it adds an external dependency for a single-user CLI tool with no concurrent access requirements.

## Decision 7: Audit Log Format

**Decision**: Append-only JSONL file at `runs/{run_id}/audit.json`, one JSON object per node execution. Not PII-filtered (per spec clarification — privileged engineer artifact).
**Rationale**: JSONL is streamable (tail -f during runs), grep-friendly, and trivially parseable. Per-node granularity matches LangSmith's trace structure, enabling cross-validation (US4 acceptance scenario 3).
**Rejected alternative**: Structured SQLite audit log. Rejected because it adds query complexity without benefit — the audit log is read sequentially and the volume per run (~50-100 entries) doesn't justify indexed storage.

## Decision 8: PII Detection Approach

**Decision**: Regex + heuristic pattern matching for PII types (SSN, phone, email, physical address, financial identifiers). Sensitive-attribute keyword filter for constitutionally prohibited inferences.
**Rationale**: Regex is fast, deterministic, and has no false-negative rate for well-formed PII patterns (SSN format, email format). The sensitive-attribute filter is keyword-based because the categories (health, religion, orientation) map to known vocabulary.
**Rejected alternative**: NER-based PII detection (spaCy/Presidio). Rejected because it adds a heavy dependency (~500MB model), has variable recall on non-standard PII formats, and the regex approach is sufficient for the patterns we need to catch in v1.

## Decision 9: HTTP Client

**Decision**: httpx (async-capable) with tenacity for retries.
**Rationale**: httpx is the modern Python HTTP client with native async support, which aligns with LangGraph's async execution. tenacity provides declarative retry policies with exponential backoff, cleaner than manual retry loops.
**Rejected alternative**: aiohttp. Rejected because httpx has a simpler API, supports both sync and async, and is more actively maintained. The async performance difference is negligible for our volume (~60 requests/run).

## Decision 10: Logging Framework

**Decision**: structlog with JSON renderer feeding both console output and audit log.
**Rationale**: structlog's bound loggers carry context (run_id, node, iteration) through the call chain without threading it manually. The JSON renderer output is directly compatible with the audit log format.
**Rejected alternative**: stdlib logging with JSON formatter. Rejected because structlog's context binding is significantly cleaner for structured per-node metadata and reduces boilerplate in every node.
