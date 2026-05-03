# Node Contracts

Each node is a function `(ResearchState) -> dict` that reads specific state fields and returns a partial state update. All nodes are decorated with `@traceable` (LangSmith) and wrapped in `BudgetGuard`.

## planner

**Reads**: `target`, `iteration`, `gaps`, `validated_claims`
**Writes**: `plan` (ResearchPlan), `iteration` (incremented)
**Model**: Claude Opus 4
**Prompt**: `prompts/planner.md`
**Behavior**: On iteration 0, generates a full research plan from the target profile. On iteration >0, refines the plan based on gaps and existing claims. Sub-questions are prioritized by dimension coverage and remaining budget.

## search_orchestrator

**Reads**: `plan.sub_questions`, `budget`
**Writes**: `search_turns` (appended), `budget.used_search_calls` (incremented)
**Model**: Gemini 2.5 Flash (for query expansion)
**Prompt**: `prompts/query_expander.md`
**Behavior**: For each sub-question, expands the initial query into 2-3 variants via LLM. Routes each query to the appropriate search provider based on intent. Caches results via SearchCache. Stops dispatching if search call budget would be exceeded.

## extractor

**Reads**: `search_turns` (latest iteration), `sources`
**Writes**: `claims` (appended), `entities` (appended), `relations` (appended), `sources` (appended)
**Model**: GPT-4.1
**Prompt**: `prompts/extractor.md`
**Behavior**: For each search result with content, extracts claims, entities, and relations as structured Pydantic output. Each claim carries source URLs. Content is wrapped via `guardrails.wrap_untrusted_content()` before insertion into the prompt. PII filter applied to each extracted claim.

## validator

**Reads**: `claims` (unvalidated from current iteration), `sources`, `validated_claims` (prior)
**Writes**: `validated_claims` (appended)
**Model**: GPT-4.1
**Prompt**: `prompts/validator.md`
**Behavior**: Cross-references each claim against all known sources. Classifies source tiers. Computes confidence score using `confidence.py` formula. Claims below 0.5 confidence with <2 independent domains are labeled "inferred, unverified". Claims that contradict higher-confidence claims are flagged.

## reflector

**Reads**: `validated_claims`, `budget`, `plan`, `gaps`
**Writes**: `gaps` (updated), `terminated`, `termination_reason`
**Model**: Claude Opus 4
**Prompt**: `prompts/reflector.md`
**Behavior**: Evaluates research progress vs. remaining budget. Decides one of three actions:
- **continue**: Gaps remain and budget allows another iteration. Returns to planner.
- **pivot**: Coverage is uneven; generates revised gap list for planner to address.
- **terminate**: Budget nearly exhausted, or all dimensions sufficiently covered. Proceeds to graph_builder.

## graph_builder

**Reads**: `validated_claims`, `entities`, `relations`
**Writes**: `entities` (canonicalized/deduplicated), `relations` (deduplicated)
**Model**: None (deterministic)
**Behavior**: Builds in-memory identity graph from entities and relations. Canonicalizes entities by fuzzy name matching + entity type + attribute overlap. Deduplicates relations by subject+predicate+object. Exports `graph_export.json`. If Neo4j is available, writes graph via idempotent MERGE queries. If Neo4j is unavailable, skips DB write and logs a warning.

## risk_analyzer

**Reads**: `validated_claims`, `entities`, `relations`
**Writes**: `risk_flags`
**Model**: Claude Opus 4
**Prompt**: `prompts/risk_analyzer.md`
**Behavior**: Analyzes validated claims and graph structure for risk patterns from the taxonomy. Assigns severity (Low/Medium/High/Critical) based on evidence strength and pattern severity. Each RiskFlag references supporting claim IDs. COVERAGE_GAP flags are generated for dimensions with zero or low-confidence claims. OTHER flags require a justification field.

## reporter

**Reads**: all state fields
**Writes**: none (side effects only)
**Model**: Claude Opus 4
**Prompt**: `prompts/reporter.md`
**Behavior**: Generates `report.md` (Markdown) and `report.json` (structured). Report sections: executive summary, target profile, research methodology, findings by dimension, risk flags (grouped by category, sorted by severity), claim inventory with provenance, identity graph summary, scope and limitations, budget consumption. Final `check_output_safety()` guardrail applied before write.
