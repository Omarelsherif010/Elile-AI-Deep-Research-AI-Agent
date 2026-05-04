# Demo Video Walkthrough Guide

A structured guide for recording an 8-12 minute demo of the Deep Research AI Agent.

---

## Act 1 — Architecture Overview (~2 min)

### What to show

1. **Open `README.md`** — scroll to the pipeline diagram. Explain the 8-node LangGraph flow:
   - Planner → Search Orchestrator → Extractor → Validator → Reflector (loop) → Graph Builder → Risk Analyzer → Reporter
   - The reflector creates the iterative loop — it decides whether to continue researching, pivot, or terminate

2. **Multi-model routing** — highlight the model table:
   - GPT-4.1 for reasoning (planner, reflector, risk analyzer, reporter)
   - GPT-5.4 Mini for extraction + validation (runs 30-60x per investigation)
   - Gemini 3 Flash for query expansion (10x cheaper for high-fanout work)
   - Show `src/research_agent/tools/llm.py` — the `ROLE_TO_MODEL` mapping and automatic fallback

3. **Ethical constitution** — mention the 10 operating principles from `CLAUDE.md`:
   - Public sources only, no PII synthesis, no sensitive attribute inference
   - Every claim requires source URLs, mandatory scope-and-limitations section
   - Coverage gaps are findings, not failures

### Key talking points
- "Three distinct AI models, each chosen for cost-performance at their specific task"
- "The reflector creates a feedback loop — it evaluates what's been found and decides where to dig deeper"
- "Budget enforcement is in state, not in code paths — hard caps on iterations, search calls, and dollars"

---

## Act 2 — Live Investigation Walkthrough (~2 min)

### What to show

1. **Show the CLI command** that produced the investigation:
   ```bash
   python -m research_agent run \
     --target "Timothy Overturf" \
     --role "CEO" \
     --org "Sisu Capital" \
     --max-iterations 4
   ```

2. **Open `runs/timothy_overturf/report.md`** — walk through:
   - Executive Summary (5 bullet points, the most important findings)
   - Risk Flags section — highlight the CRITICAL SEC enforcement action
   - Scope and Limitations — emphasize this is mandatory, not optional

3. **Quick glance at `runs/timothy_overturf/report.json`** — note it has the full machine-readable data:
   - 670 validated claims
   - 6 risk flags (2 CRITICAL, 4 COVERAGE_GAP)
   - 69 entities, 258 relations

4. **Open `runs/timothy_overturf/audit.json`** — show one entry to demonstrate observability:
   - Per-node: input state hash, prompt sent, raw response, latency, tokens, cost

### Key talking points
- "The agent found a real SEC enforcement action against Timothy Overturf — this is a genuine CRITICAL regulatory finding"
- "670 claims from 60 search calls, with confidence scores from 0.3 to 0.99"
- "Every node execution is logged with 8 observability axes"

---

## Act 3 — Streamlit Demo (~2 min)

### What to show

1. **Launch the app**:
   ```bash
   streamlit run streamlit_app.py
   ```

2. **Select the Timothy Overturf run** from the sidebar dropdown

3. **Walk through each tab**:
   - **Risk Flags** — expandable cards grouped by category, color-coded by severity
   - **Claims** — sortable table with confidence scores and source tiers
   - **Identity Graph** — interactive network visualization (nodes = entities, edges = relationships)

4. **Point out the ethics footer** at the bottom: "This system operates exclusively on public sources. No sensitive attributes were inferred."

### Key talking points
- "The Streamlit app renders the same report.json the CLI produces — it's a viewer, not a separate system"
- "Risk flags are grouped by category and sorted by severity, just like the markdown report"
- "The identity graph shows 69 entities and their relationships — you can hover over nodes for details"

---

## Act 4 — Eval Suite (~2 min)

### What to show

1. **Open `eval/personas/`** — show the three persona files:
   - `persona_real_public.yaml` — Satya Nadella (real public figure, 10 planted facts)
   - `persona_synthetic_a.yaml` — Aria Vellinor (synthetic, planted facts on GitHub Pages)
   - `persona_synthetic_b.yaml` — Dorian Ashcroft (synthetic, planted facts on GitHub Pages)

2. **Open one persona YAML** — show the planted facts structure:
   - Each fact has: statement, difficulty tier (easy/medium/hard), match strategy (exact/fuzzy/semantic), source URLs

3. **Show eval metrics** (from `demo_results/eval/`):
   - Precision, recall by tier, risk recall, expected calibration error (ECE)
   - Explain the 3 matching strategies: exact string, fuzzy (rapidfuzz), semantic (OpenAI embeddings)

4. **Explain the synthetic persona limitation honestly**:
   - The plant site is live on GitHub Pages
   - Brave Search doesn't index low-authority GitHub Pages sites
   - This is a real-world OSINT limitation, not a code bug
   - The eval framework correctly measures 0% recall when the search provider returns no results

### Key talking points
- "The eval suite tests three things: can the agent find facts (recall), are its claims accurate (precision), and are confidence scores well-calibrated (ECE)"
- "Synthetic personas demonstrate the eval framework's design — planted facts with ground truth — but search providers can't find low-authority pages"
- "The real public persona (Satya Nadella) produces meaningful recall because his information is widely indexed"

---

## Act 5 — Code Quality & Design Decisions (~2 min)

### What to show

1. **Prompts-as-code** — open `prompts/risk_analyzer.md`:
   - Structured sections: Role, Context, Task, Output Format, Constraints, Examples, Notes
   - Version-controlled, reviewed like code
   - Show the Examples section — few-shot prompting with edge cases

2. **Pydantic schemas** — open `src/research_agent/schemas.py`:
   - All inter-node data is typed (ValidatedClaim, RiskFlag, Entity, Relation, etc.)
   - Show how RiskFlag has typed enums for category and severity

3. **Confidence scoring** — open `src/research_agent/confidence.py`:
   - Deterministic 4-factor formula, not LLM-based
   - Testable, calibration-measurable

4. **Guardrails** — open `src/research_agent/guardrails.py`:
   - Input sanitization, PII regex filtering, prompt injection defense
   - Output safety check on every report

5. **Design decisions table** from README — highlight:
   - Multi-model routing: why 3 models instead of 1
   - Deterministic confidence: why not let the LLM assign confidence
   - LangGraph over CrewAI: explicit topology vs magic orchestration

### Key talking points
- "Every architectural choice has a written rationale and one rejected alternative"
- "Prompts are first-class code — version-controlled, structured, with examples and constraints"
- "Confidence is deterministic because we need to measure calibration in the eval suite"

---

## Closing (~30 sec)

Summarize in one sentence: "This is a production-grade research agent that finds real regulatory risk using multi-model orchestration, with every claim provenanced, every decision auditable, and every limitation disclosed."
