# Data Model: Deep Research AI Agent

**Phase**: 1 (Design & Contracts)
**Date**: 2026-05-03

## Core Schemas (schemas.py)

All models are Pydantic v2 BaseModel subclasses. All inter-node data uses these types — no untyped dicts cross module boundaries (Principle 7).

### Input

```
TargetProfile
├���─ name: str                       # required; max 200 chars
├── aliases: list[str]              # optional alternate names
├── role: str | None                # e.g., "CEO", "former senator"
├���─ organization: str | None        # e.g., "Acme Corp"
├── context: str | None             # freeform context
└── geographic_hint: str | None     # e.g., "Dubai, UAE"
```

### Planning

```
ResearchPlan
├── iteration: int                  # which iteration this plan targets
├── sub_questions: list[SubQuestion]
└── plan_notes: str                 # planner's reasoning

SubQuestion
├── id: str                         # e.g., "sq-001"
├── dimension: str                  # biographical, professional, financial, network, statements, risk
├── question: str                   # natural language research question
├── rationale: str                  # why this question matters
├── answer_criteria: str            # what would constitute a satisfactory answer
├── initial_query: str              # seed search query
└── priority: int                   # 1=highest
```

### Search

```
SearchResult
├── url: str
├── title: str
├── snippet: str
├── content: str | None             # full text if fetched; None if snippet-only
├── retrieved_at: datetime
└── provider: str                   # "brave", "exa", "firecrawl"

SearchTurn
├── iteration: int
├── query: str
├── provider: str
└── results: list[SearchResult]

Source
├── url: str
├── domain: str                     # registrable domain (e.g., "sec.gov")
├── tier: int                       # 1-4, classified by LLM
├── retrieved_at: datetime
└── robots_allowed: bool
```

### Claims & Validation

```
Claim
├── id: str                         # uuid
├── subject: str                    # entity name (target or related)
├── predicate: str                  # e.g., "served as CEO of"
├── object: str                     # e.g., "Acme Corp"
├── attributes: dict[str, str]      # temporal bounds, qualifiers
├── source_urls: list[str]          # ≥1 required
├── extraction_confidence: float    # LLM's self-reported extraction confidence
└── asserted_at: datetime | None    # when the claim was true (if temporal)

ValidatedClaim(Claim)               # extends Claim
├── confidence: float               # [0, 1] from confidence formula
├── supporting_sources: list[Source] # sources that corroborate
├── contradicts: list[str]          # claim IDs that contradict this claim
└── validation_notes: str           # explanation of confidence scoring
```

### Identity Graph

```
Entity
├── id: str                         # uuid
├── type: EntityType                # PERSON | ORGANIZATION | EVENT
├── canonical_name: str             # deduplicated canonical form
├── aliases: list[str]              # alternate names encountered
├── attributes: dict[str, str]      # role, description, dates, etc.
└── confidence: float               # how certain we are this entity is real

Relation
├── subject_entity_id: str          # Entity.id
├── predicate: str                  # e.g., "employed_by", "associated_with"
├── object_entity_id: str           # Entity.id
├── attributes: dict[str, str]      # temporal bounds, qualifiers
├── confidence: float               # derived from supporting claims
└── evidence_claim_ids: list[str]   # ValidatedClaim.id references
```

### Risk

```
RiskCategory (enum)
├── REGULATORY
├── REPUTATIONAL
├── NETWORK
├── FINANCIAL
├── INCONSISTENCY
├── COVERAGE_GAP
└── OTHER

RiskSeverity (enum)
├── LOW
├── MEDIUM
├── HIGH
└── CRITICAL

RiskFlag
├── type: RiskCategory
├── severity: RiskSeverity          # Low / Medium / High / Critical
├── description: str
├── evidence_claim_ids: list[str]   # ValidatedClaim.id references
├── confidence: float
└── justification: str | None       # required when type == OTHER
```

### Budget & Observability

```
Budget
├── max_iterations: int             # default 8
├── used_iterations: int
├── max_search_calls: int           # default 60
├── used_search_calls: int
├── max_dollars: float              # default 5.0
├── used_dollars: float
├── max_seconds_per_iteration: int  # default 180; constitution Principle 4
├── used_seconds_current_iteration: float  # reset each iteration; BudgetGuard enforces
└── last_iteration_cost: float      # for reflector cost projection

AuditEntry
├── timestamp: datetime
├── node: str
├── input_state_hash: str           # sha256 of input state
├── prompt_filled: str              # rendered prompt (template + vars)
├── raw_response: str               # model's raw output
├── parsed_output: dict             # Pydantic model serialized
├── latency_ms: float
├── tokens_in: int
├── tokens_out: int
├── dollars: float
└── retries: list[RetryRecord]      # reason + attempt for each retry

RetryRecord
├── attempt: int
├── reason: str
└── latency_ms: float
```

## ResearchState (state.py)

TypedDict used as the LangGraph state. All fields are optional except `run_id` and `target`.

```
ResearchState (TypedDict)
├── run_id: str
├── target: TargetProfile
├── iteration: int
├── plan: ResearchPlan | None
├── search_turns: list[SearchTurn]
├── claims: list[Claim]
├── validated_claims: list[ValidatedClaim]
├── entities: list[Entity]
├── relations: list[Relation]
├── sources: list[Source]
├── risk_flags: list[RiskFlag]
├── gaps: list[str]                 # dimensions not yet explored
├── budget: Budget
├── audit_entries: list[AuditEntry]
├── terminated: bool
└── termination_reason: str
```

## State Transitions

```
Initial state (from CLI):
  target = TargetProfile from user input
  iteration = 0
  budget = Budget(defaults)
  all lists = []
  terminated = False

planner:
  reads: target, iteration, gaps, validated_claims
  writes: plan, iteration += 1

search_orchestrator:
  reads: plan.sub_questions
  writes: search_turns (appends), budget.used_search_calls

extractor:
  reads: search_turns (latest), sources
  writes: claims (appends), entities (appends), relations (appends), sources (appends)

validator:
  reads: claims (unvalidated), sources
  writes: validated_claims (appends), claims (updates confidence)

reflector:
  reads: validated_claims, budget, plan, gaps
  writes: gaps (updated), terminated, termination_reason
  decides: continue | pivot | terminate

graph_builder:
  reads: validated_claims, entities, relations
  writes: entities (canonicalized), relations (deduplicated)
  side effect: Neo4j MERGE writes (if available), JSON graph export

risk_analyzer:
  reads: validated_claims, entities, relations
  writes: risk_flags

reporter:
  reads: all state
  writes: none (side effect: report.md, report.json to filesystem)
```

## Entity Relationships

```
TargetProfile ──(investigated_by)──► ResearchPlan
ResearchPlan ──(generates)──► SubQuestion ──(drives)──► SearchTurn
SearchTurn ──(yields)──► SearchResult ──(extracted_into)──► Claim
Claim ──(validated_as)──► ValidatedClaim
ValidatedClaim ──(supported_by)──► Source
ValidatedClaim ──(contributes_to)──► Entity
ValidatedClaim ──(contributes_to)──► Relation
ValidatedClaim ──(triggers)──► RiskFlag
Entity ──(connected_via)──► Relation ──(connects_to)──► Entity
```
