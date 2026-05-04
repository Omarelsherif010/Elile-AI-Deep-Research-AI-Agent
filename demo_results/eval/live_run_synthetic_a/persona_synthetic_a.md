# persona_synthetic_a — Eval Report

**Run ID**: `20260504_102832`  
**Timestamp**: 2026-05-04T10:44:37.909400+00:00  

## Summary

| Metric | Value |
|--------|-------|
| Overall Pass | FAIL |
| Precision | 0.52  |
| Risk Recall | 0.00 |
| Cost | $0.00 |
| Duration | 950.2s |

## Recall by Tier

| Tier | Recall | Found / Total |
|------|--------|---------------|
| easy | 0.00 | 0 / 4 |
| medium | 0.00 | 0 / 4 |
| hard | 0.00 | 0 / 4 |

## Precision

- **Rate**: 0.52
- **Sample size**: 54
- **Automated**: Yes



## Calibration

| Confidence Range | Claims | Matched | Observed Precision | Bar |
|------------------|--------|---------|-------------------|-----|
| (0.0, 0.2] | 0 | 0 | N/A |  |
| (0.2, 0.4] | 0 | 0 | N/A |  |
| (0.4, 0.6] | 54 | 0 | 0.00 |  |
| (0.6, 0.8] | 0 | 0 | N/A |  |
| (0.8, 1.0] | 0 | 0 | N/A |  |

**Expected Calibration Error (ECE)**: 0.4861

## Risk Recall

| Planted Risk | Matched | Severity Match |
|--------------|---------|---------------|
| `risk_a01` | No | No |

## Fact Matches

| Fact ID | Strategy | Score | Matched Claim | Confidence |
|---------|----------|-------|---------------|------------|
| `fact_a01` | exact | 0.0 | — | — |
| `fact_a02` | fuzzy | 0.0 | — | — |
| `fact_a03` | fuzzy | 0.0 | — | — |
| `fact_a04` | exact | 0.0 | — | — |
| `fact_a05` | fuzzy | 0.0 | — | — |
| `fact_a06` | fuzzy | 0.0 | — | — |
| `fact_a07` | fuzzy | 0.0 | — | — |
| `fact_a08` | fuzzy | 0.0 | — | — |
| `fact_a09` | semantic | 0.0 | — | — |
| `fact_a10` | fuzzy | 0.0 | — | — |
| `fact_a11` | semantic | 0.0 | — | — |
| `fact_a12` | fuzzy | 0.0 | — | — |

## Cost Summary

| Metric | Value |
|--------|-------|
| Cost | $0.00 |
| Duration | 950.2s |
| Iterations | 0 |
| Search Calls | 42 |

## Success Criteria

| Criterion | Status |
|-----------|--------|
| High Confidence Precision | PASS |
| Easy Recall | FAIL |
| Risk Recall | FAIL |