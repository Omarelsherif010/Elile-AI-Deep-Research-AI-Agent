# Feature Specification: Deep Research AI Agent

**Feature Branch**: `001-deep-research-agent`
**Created**: 2026-05-03
**Status**: Draft
**Input**: User description: "Build a Deep Research AI Agent for iterative web research, claim extraction, risk analysis, and auditable reporting on target individuals."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — End-to-End Research Run (Priority: P1)

As a risk analyst, I supply a target person's name plus minimal context (aliases, role, organization) and within roughly ten minutes I receive: a Markdown risk report, a queryable identity graph, and a JSON audit log.

**Why this priority**: This is the core value proposition. Every other story depends on this pipeline existing and completing successfully. Without end-to-end execution, there is no product.

**Independent Test**: Submit a known public figure's name via the CLI. Verify that three output artifacts are produced (report, graph, audit log), that the run completes within budget caps, and that the report contains at least one validated claim with provenance.

**Acceptance Scenarios**:

1. **Given** a valid target name and optional context fields, **When** I invoke the research agent, **Then** the system produces a Markdown report, a structured JSON report, a populated identity graph, an audit log, and a graph export file in the run output directory.
2. **Given** a valid target name, **When** the run completes, **Then** total cost is under USD 5, total iterations are at most 8, and total search calls are at most 60.
3. **Given** a target with very thin public coverage, **When** the run completes, **Then** the report explicitly documents "coverage gap" as a finding rather than generating fabricated content.
4. **Given** a run in progress, **When** a budget cap is reached before all research dimensions are explored, **Then** the system terminates gracefully, produces a report with available findings, and notes "budget exhausted" in the report.

---

### User Story 2 — Claim Provenance and Confidence Transparency (Priority: P1)

As a risk analyst, I can trace any claim in the report back to its source URLs and see why the agent assigned its confidence score.

**Why this priority**: Provenance and explainability are constitutional requirements (Principles 2 and 10). Without them, the report is not trustworthy and the assessment fails its primary evaluation criteria.

**Independent Test**: Open the generated report and select any claim. Verify it links to at least one source URL. Verify the confidence score is accompanied by the factors that determined it (source count, source tier, cross-validation result).

**Acceptance Scenarios**:

1. **Given** a completed report, **When** I inspect any claim with confidence > 0.5, **Then** it is supported by at least 2 independent source domains OR 1 Tier-1 source (government, court, regulatory filing).
2. **Given** a completed report, **When** I inspect any claim derived solely from LLM inference, **Then** it is labeled "inferred, unverified" and its confidence is capped at 0.4.
3. **Given** the JSON report, **When** I look up any claim, **Then** I find the source URLs, the confidence score, the scoring factors, and the validation method used.

---

### User Story 3 — Risk Flag Presentation (Priority: P2)

As a risk analyst, I see risk flags grouped by type with severity ratings (Low / Medium / High / Critical) and supporting evidence chains, so I can prioritize my review.

**Why this priority**: Risk surfacing is the primary analytical output beyond raw claims. It transforms data into actionable intelligence. However, it depends on extraction and validation (US1, US2) being functional first.

**Independent Test**: Run the agent against an eval persona with planted risk patterns. Verify the report groups flags by category, assigns severity, and links each flag to supporting claims with source chains.

**Acceptance Scenarios**:

1. **Given** a completed research run, **When** I review the risk section of the report, **Then** risk flags are grouped by category (Regulatory, Reputational, Network, Financial, Inconsistency, Coverage Gap, Other).
2. **Given** a risk flag in the report, **When** I inspect it, **Then** I see a severity (Low, Medium, High, or Critical), a description, and references to the specific validated claims that support it.
3. **Given** an eval persona with planted risk patterns, **When** I run the agent, **Then** at least 80% of planted risk patterns are surfaced in the risk section.

---

### User Story 4 — Run Replay and Observability (Priority: P2)

As an engineer, I can replay any completed run step-by-step from distributed traces and from the local audit log, seeing exactly what each processing step received, sent, and produced.

**Why this priority**: Observability is a constitutional requirement (Principle 6) and a key evaluation surface. Graders will inspect traces to verify architectural claims.

**Independent Test**: Complete a research run. Open the distributed trace and verify every processing step is visible with its inputs, outputs, latency, token counts, cost, and retry history. Independently verify the same information is available in the local audit log JSON.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** I open the distributed trace, **Then** every processing step is visible with: input state hash, prompt sent, raw model response, parsed output, latency, token counts (in/out), cost, and retry attempts.
2. **Given** a completed run, **When** I read the local audit log, **Then** it contains the same eight per-step axes as the distributed trace, in structured JSON format.
3. **Given** a completed run, **When** I compare the trace and the audit log, **Then** they are consistent — the same steps, the same inputs and outputs, the same cost figures.

---

### User Story 5 — Eval Suite Execution (Priority: P2)

As an engineer, I can run an evaluation suite against three test personas and see recall, precision, confidence-calibration, and risk-recall metrics.

**Why this priority**: Evals are how we verify that the system works correctly and that changes don't introduce regressions. Required by Principle 5 and the assessment's emphasis on production sensibility.

**Independent Test**: Run the eval suite. Verify it executes against all three personas, produces a metrics report, and the metrics include recall (easy/medium/hard), precision, confidence calibration, and risk recall.

**Acceptance Scenarios**:

1. **Given** three eval personas with planted ground truth, **When** I run the eval suite, **Then** it executes end-to-end against all three personas within budget caps.
2. **Given** a completed eval run, **When** I review the metrics report, **Then** I see recall at three difficulty tiers, precision on a sample of 30 claims, confidence calibration (claims > 0.8 confidence vs. actual precision), and risk recall.
3. **Given** a passing eval run, **When** I inspect the results, **Then** recall on easy facts is at least 70%, precision is at least 90%, claims above 0.8 confidence achieve at least 95% precision, and risk recall is at least 80%.

---

### Edge Cases

- **Ambiguous target name**: When the target name is common and shared by multiple public figures, the system uses provided context fields (role, organization, aliases) to disambiguate. If ambiguity persists, the report flags "identity ambiguity" as a finding and presents claims grouped by potential identity.
- **All search providers fail**: When all search providers return no results or are unavailable, the system reports zero validated claims, documents the queries attempted and providers used, and produces a "coverage gap" report rather than fabricating content.
- **Budget exhaustion on high-coverage target**: When a target has extensive coverage that exceeds budget before all research dimensions are explored, the system terminates gracefully, reports findings gathered so far, and notes which dimensions were not fully explored.
- **Provider temporary unavailability**: When a search provider is temporarily unavailable, the system falls back to alternative providers for that intent. If all providers for a given intent are down, it skips that search intent, logs the failure, and continues.
- **Prompt-injection in fetched content**: When extracted web content contains prompt-injection attempts, fetched content is delimited as data (not instructions) in prompts. Output schema validation rejects malformed responses. The system logs the incident and retries without the problematic content.
- **PII in audit log**: The audit log stores raw model responses and may contain PII from web sources. It is a privileged engineer-only artifact — PII filtering is NOT applied to it (unlike the report and graph). Access control, not content scrubbing, is the protection mechanism.
- **Non-English sources**: When the system encounters non-English sources during search, it flags them in the report but does not extract or translate their content in v1.

## Clarifications

### Session 2026-05-03

- Q: When the graph database is unavailable, should the system fail or degrade? (FR-07 says MUST but Assumptions said "skipped if unavailable.") → A: In-memory graph + JSON export always produced; only the live database write is skipped when DB is unavailable.
- Q: Should the audit log be PII-filtered like other persisted artifacts (report, graph)? → A: No. The audit log is a privileged engineer-only artifact. Access control protects it, not content scrubbing. PII filtering would destroy its diagnostic value.
- Q: What severity scale should risk flags use? → A: Four-level: Low / Medium / High / Critical.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-01**: System MUST accept a target profile consisting of a name (required) plus optional aliases, role, organization, and freeform context fields.
- **FR-02**: System MUST generate a research plan covering at minimum: biographical, professional history, financial connections, network/associations, public statements, and risk-surface dimensions.
- **FR-03**: System MUST iteratively search using at least two distinct search providers, refining queries based on prior findings through a query-expansion step.
- **FR-04**: System MUST extract entities (Person, Organization, Event), relations between entities, and claims about the target — each with source attribution — as validated structured output.
- **FR-05**: System MUST cross-validate claims across sources and assign a confidence score in the range [0, 1] using a documented multi-factor formula.
- **FR-06**: System MUST detect risk patterns from a typed taxonomy with at minimum these categories: Regulatory, Reputational, Network, Financial, Inconsistency, Coverage Gap, Other. Each risk flag MUST be assigned a four-level severity: Low, Medium, High, or Critical.
- **FR-07**: System MUST build a typed identity graph in memory from validated claims, canonicalizing entities to avoid duplicates, and MUST export it as a JSON file. The system SHOULD write the graph to a live graph database when available; if the database is unavailable, the run continues and the JSON export serves as the primary graph artifact.
- **FR-08**: System MUST produce per run: a human-readable Markdown report, a structured JSON report, a JSON graph export, and a structured audit log.
- **FR-09**: System MUST log every processing step with structured per-step metadata: input hash, prompt, response, parsed output, latency, tokens, cost, retries.
- **FR-10**: System MUST provide a command-line interface that accepts a target name, optional context, and optional output directory.
- **FR-11**: System SHOULD provide a visual demo interface for presenting results interactively (lower priority; dependent on available time).
- **FR-12**: System MUST support execution of an evaluation suite against three test personas, emitting a metrics report with recall, precision, confidence calibration, and risk recall.

### Key Entities

- **TargetProfile**: The person under investigation — name, aliases, role, organization, freeform context fields. The root input to every research run.
- **Claim**: A factual assertion about the target — text, confidence score, source URLs, validation status, scoring factors, and the validation method used. The atomic unit of evidence.
- **Entity**: A node in the identity graph — typed as Person, Organization, or Event — with a canonical name and descriptive attributes. Deduplicated across sources.
- **Relation**: A typed edge between two entities — relationship type, temporal bounds (if known), and references to the claims that support it.
- **RiskFlag**: A detected risk pattern — category (from the typed taxonomy), severity (Low / Medium / High / Critical), human-readable description, and references to the supporting claims and evidence chain.
- **ResearchPlan**: The dimensions and queries the agent intends to explore for a given target. Generated at the start of a run and refined by reflection.
- **Budget**: The resource limits for a run — iteration cap, search call cap, dollar cap, per-iteration time cap. Tracked in state and enforced at every processing step.
- **AuditEntry**: A structured log record for one processing step — input state hash, prompt sent, raw response, parsed output, latency, token counts, cost, and retry history. Privileged engineer-only artifact; not PII-filtered (raw responses preserved for diagnostic value).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-01**: Given an eval persona with planted easy-tier facts, the system recalls at least 70% of them.
- **SC-02**: Given an eval persona with planted hard-tier facts, the system recalls at least 40% of them.
- **SC-03**: On a manual sample of 30 extracted claims from eval runs, at least 90% are factually accurate (precision ≥ 90%).
- **SC-04**: Claims assigned confidence above 0.8 achieve at least 95% precision on manual review (confidence calibration).
- **SC-05**: Given eval personas with planted risk patterns, the system surfaces at least 80% of them (risk recall ≥ 80%).
- **SC-06**: All three eval personas complete their research runs within the defined budget caps (≤ 8 iterations, ≤ 60 search calls, ≤ USD 5).
- **SC-07**: An end-to-end run on a real public figure with thin coverage produces a report that documents "coverage gap" as the finding rather than fabricating content.
- **SC-08**: Every claim in the report is traceable to at least one source URL. An analyst can navigate from claim to source in a single step.
- **SC-09**: Every processing step in a completed run is reconstructable from either the distributed trace or the local audit log.
- **SC-10**: An end-to-end run on a well-known public figure completes in roughly 10 minutes or less under normal network and provider conditions.

## Assumptions

- The target is a public figure with some presence in publicly accessible web sources. The system is not designed for private individuals with no public footprint.
- Search provider API keys are configured and the providers are available. Temporary outages are handled by fallback; permanent unavailability of all providers is not handled in v1.
- The graph database is available (free-tier cloud instance or local) for live querying. If unavailable, the system still builds the identity graph in memory and exports it as JSON; only the live database write is skipped.
- Evaluation personas and their planted ground truth are maintained in the repository. The GitHub Pages microsite for synthetic personas is deployed and accessible during eval runs.
- "Roughly ten minutes" (SC-10) is a goal, not a hard requirement. Actual run time depends on target complexity, search provider latency, and model response times. Budget caps (SC-06) are the hard limits.
- The visual demo interface (FR-11) is best-effort and will only be built if core functionality (FR-01 through FR-10, FR-12) is complete.
- Multi-model routing is a design constraint: the system uses different models for different processing roles to optimize cost, quality, and speed. Specific model assignments may be adjusted based on availability.
- Non-English sources encountered during search are flagged in the report but not translated or extracted in v1.
