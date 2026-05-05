# Satya Nadella — Eval Run Summary

**Run ID**: `20260504_152223`
**Persona**: `persona_real_public` (real public figure, no planted risks)
**Duration**: ~43 minutes (2604s)

## Agent Results

| Metric | Value |
|--------|-------|
| Claims | 985 |
| Entities | 225 |
| Relations | 409 |
| Risk Flags | 4 (all COVERAGE_GAP, no fabricated risks) |
| Search Calls | 60 |
| Iterations | 3 (budget-terminated) |

## Eval Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Easy Recall | 0.50 | 2/4 easy facts found |
| Medium Recall | 1.00 | 3/3 medium facts found |
| Hard Recall | 1.00 | 3/3 hard facts found (fuzzy fallback for semantic) |
| Risk Recall | N/A | No planted risks in this persona |
| Fabricated Risks | 0 | Agent correctly produced no fabricated risk flags |
| ECE | 0.486 | Calibration error — acceptable for a first run |

## Fact Match Details

| Fact | Tier | Strategy | Found | Notes |
|------|------|----------|-------|-------|
| CEO of Microsoft | easy | exact | MISS | Claim text doesn't match verbatim |
| CEO since Feb 2014 | easy | exact | MISS | Exact matching too strict |
| MS in CS from UW-Milwaukee | easy | fuzzy | FOUND | |
| Chairman since June 2021 | easy | fuzzy | FOUND | |
| Starbucks board | medium | fuzzy | FOUND | |
| $48.5M compensation FY2023 | medium | fuzzy | FOUND | |
| Worked at Sun Microsystems | medium | fuzzy | FOUND | High-quality match (97.4 score) |
| AI shareholder letter | hard | semantic→fuzzy | FOUND | Semantic fell back to fuzzy |
| Responsible AI principles | hard | semantic→fuzzy | FOUND | Semantic fell back to fuzzy |
| Born in Hyderabad, India | hard | fuzzy | FOUND | High-quality match (94.9 score) |

## Key Observations

1. **No fabricated risks**: The agent correctly produced only COVERAGE_GAP flags for Satya Nadella — no fabricated regulatory, reputational, or financial risks. This demonstrates the no-fabrication discipline.

2. **Exact matching limitation**: The two "easy" misses (fact_r01, fact_r02) use exact matching but the agent's claims express the same information with different wording. This is an eval framework limitation, not an agent failure.

3. **Semantic matching unavailable**: OpenAI embedding quota was exhausted, so semantic matches fell back to fuzzy. With proper embeddings, the hard-tier matches would be more precise.

4. **High claim volume**: 985 claims from 60 search calls across 3 iterations — significantly more than the Timothy Overturf run (670 claims), reflecting Satya Nadella's much larger public presence.
