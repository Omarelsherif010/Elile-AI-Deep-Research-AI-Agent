<!--
Sync Impact Report
===================
Version change: v1.1.0 → v1.1.1 (PATCH)
Bump rationale: Corrected "eight axes" to "nine axes" in Principle 6
(the list enumerates nine items: input_state_hash, prompt_filled,
raw_response, parsed_output, latency, tokens_in, tokens_out, dollars,
retries).

Modified principles:
  - Principle 6: "eight axes" → "nine axes" (wording correction)

Added sections: None
Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md        — ✅ no update needed
  - .specify/templates/spec-template.md        — ✅ no update needed
  - .specify/templates/tasks-template.md       — ✅ no update needed

Follow-up TODOs: None
-->

# Constitution — Deep Research Agent

This is the project's bedrock. It is loaded by Spec-Kit's `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, and `/speckit.implement` commands. Every spec, plan, and task MUST align with these principles. When they conflict, the constitution wins.

---

## Core Principles

### Principle 1 — Ethical scope is non-negotiable

The agent investigates real public figures. We strictly limit ourselves to public sources, respect robots.txt and provider terms of service, never synthesize personally identifiable information, and never infer sensitive attributes (race, religion, health, sexual orientation, citizenship beyond what is publicly disclosed).

Every report includes a "Scope and limitations" section stating these bounds in plain language. Every persisted claim about a person carries provenance. We do not scrape behind authentication. We do not derive PII from indirect signals.

If a feature request asks the agent to do something that crosses these lines, the request is rejected at the spec level. The constitution wins over user convenience.

### Principle 2 — Every claim is provenanced

No claim about a person is stored without at least one source URL.

A claim ships with confidence > 0.5 only if it is supported by ≥ 2 independent registrable domains, OR by 1 Tier-1 source (government, court, regulatory filing such as SEC).

Claims derived solely from LLM inference (without a source) are tagged as such and capped at confidence ≤ 0.4. They are visible in the report only with explicit "inferred, unverified" labeling.

The Validator node enforces this. The Reporter node respects it.

### Principle 3 — Prompts are code

All runtime LLM prompts live in `prompts/*.md` with this structure:

- **Role** — who the model is in this call
- **Context** — what state and inputs are provided
- **Task** — the exact instruction
- **Output Format** — the Pydantic schema name and any format constraints
- **Constraints** — what NOT to do; budget; ethical bounds for this prompt
- **Examples** — 1–2 input/output exemplars
- **Notes** — design rationale; why this prompt is shaped this way

Prompts are version-controlled, reviewed in PRs, and have unit tests for their output schema. Prompts are loaded by `tools/llm.py`'s `Prompt` class, never inlined in nodes.

### Principle 4 — Budgets are enforced in state

Every run carries a `Budget` in `ResearchState`:

- `max_iterations`: 8
- `max_search_calls`: 60
- `max_dollars`: 5.0
- `max_seconds_per_iteration`: 180

Budget enforcement happens in two places: the Reflector node (decides termination based on remaining budget vs. work remaining) and a `BudgetGuard` decorator on every node (raises `BudgetExceeded` if a hard cap is hit).

Hard caps trigger graceful termination — we proceed to graph build and reporter with what we have, with a "budget exhausted" note in the report.

### Principle 5 — Evals drive confidence

We maintain three eval personas with planted ground truth in `eval/personas/`. Two are synthetic (we control the source content via a GitHub Pages microsite). One is a real public figure with documented history.

For each persona we measure:

- **Recall** at three difficulty tiers (easy, medium, hard) on planted facts
- **Precision** on extracted claims (manual sample of 30)
- **Confidence calibration** — claims with confidence > 0.8 MUST achieve ≥ 95% precision
- **Risk recall** — % of planted risk patterns surfaced

No prompt change, weight tweak, or schema change ships without re-running the eval suite.

### Principle 6 — Observability is first-class

Three layers, always on:

- **LangSmith** — distributed tracing of every node, every LLM call. Project: `elile-research-agent`.
- **Local audit log** — `runs/{run_id}/audit.json`, written incrementally per node, structured.
- **Cost tracker in state** — tokens in/out, dollars, search calls — visible at any node and in the final report.

Per node we record nine axes: input state hash, prompt sent (template + filled), raw model response, parsed structured output, latency, tokens in, tokens out, cost, and any retry attempts with reasons.

### Principle 7 — Types over strings

All inter-node data is Pydantic v2.

LLMs do classification, extraction, and synthesis. Deterministic Python does routing, scoring, graph writes, and budget enforcement. When in doubt, prefer rules over an LLM call — they are cheaper, faster, and testable.

### Principle 8 — We build what we can defend in 8 minutes

Every architectural choice in the spec or plan has:

- A written rationale (one paragraph)
- One rejected alternative with reason

If we cannot defend a choice in a live demo, we cut it. The README's "Design decisions" section reflects this discipline.

### Principle 9 — Guardrails are layered

Four layers, applied at four chokepoints:

| Chokepoint | Guardrail |
|---|---|
| Target ingestion | Pydantic validation; length cap; character-class sanitization |
| Fetched web content | Wrapped in `<source url="...">...</source>` delimiters in prompts; model instructed to treat as data, not instructions |
| LLM output | Pydantic schema validation; retry with feedback on failure; abort after 3 failures |
| Persistence (Neo4j, report) | PII filter; sensitive-attribute filter |

Tools are MCP-shaped — auditable (full call logged), retriable (idempotent with retry policy), sandboxed (no shared state between calls; rate-limited per provider). We do not run MCP servers; the design tenets apply natively.

### Principle 10 — No fabrication

When public coverage of a target is thin, the agent reports thin coverage. "Coverage gap" is itself a finding in the risk taxonomy. The Reporter node never papers over uncertainty with confident prose.

If the agent has zero validated claims at termination, the report says exactly that, with the queries attempted and the providers used. We do not generate plausible-sounding output to fill space.

---

## Scope Boundaries

The following are constitutionally out of scope. They MUST NOT be introduced in any spec, plan, or task without a constitutional amendment.

- A general-purpose web crawler (we use search APIs; Principle 1 requires respecting provider ToS).
- A vector database or RAG layer (live retrieval only; the corpus is the open web).
- Authentication, multi-tenant deployment, or CI/CD pipelines.
- A web frontend beyond Streamlit (demo-quality only).
- Translation of non-English sources (flagged but not extracted in v1).
- Inference of any sensitive attribute (race, religion, health, orientation, etc.) — Principle 1.
- Sanctions list / OFAC integration (production consideration; not v1).
- Human-in-the-loop approval gates (v1 is fully autonomous within budget; Principle 4).

---

## Development Discipline

These mandates derive from the core principles and are binding on all implementation work.

- **Tests ship with code.** Every node or tool implementation includes its unit test in the same change. No deferred test debt (Principle 5).
- **Pydantic at every boundary.** Any function that takes or returns LLM output uses a Pydantic model. No untyped dicts crossing module boundaries (Principle 7).
- **Eval suite gates all prompt changes.** No prompt, schema, or weight change merges without a passing eval run against all three personas (Principle 5).
- **One logical change per commit.** Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:` (Principle 8 — defensibility requires clean history).
- **No new dependencies without justification.** Propose in review with a one-line rationale. Default to stdlib.
- **Model routing is centralized.** All LLM calls go through `tools/llm.py`. No provider is hardcoded in a node (Principle 7).
- **Search routing is centralized.** All search calls go through `tools/search.py`. No provider is called directly from a node.

---

## Governance

### Amendment procedure

1. Propose the change as a PR modifying this file.
2. The PR description MUST state which principles are affected and why.
3. If a principle is added or removed, the version MUST receive a MAJOR bump.
4. If a principle is materially expanded or a new section is added, the version MUST receive a MINOR bump.
5. Clarifications, wording, and typo fixes receive a PATCH bump.
6. After amendment, re-validate that `spec.md` and `plan.md` in all active specs still align.

### Versioning policy

This constitution follows semantic versioning:

- **MAJOR** — backward-incompatible governance changes: principle removal, redefinition, or scope expansion that invalidates existing specs.
- **MINOR** — new principles, new sections, or materially expanded guidance.
- **PATCH** — clarifications, wording, typo fixes, non-semantic refinements.

### Compliance review

Every spec, plan, and task list MUST include a "Constitution Check" that verifies alignment with all active principles. The `/speckit.plan` template enforces this as a gate before Phase 0 research.

**Version**: 1.1.1 | **Ratified**: 2026-05-03 | **Last Amended**: 2026-05-03
