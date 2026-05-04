# persona_synthetic_a — Eval Report

**Run ID**: ``  
**Timestamp**: 2026-05-03T18:12:40.158827+00:00  

## Summary

| Metric | Value |
|--------|-------|
| Overall Pass | PASS |
| Precision | 1.00  |
| Risk Recall | 1.00 |
| Cost | $0.85 |
| Duration | 0.0s |

## Recall by Tier

| Tier | Recall | Found / Total |
|------|--------|---------------|
| easy | 1.00 | 0 / 0 |
| medium | 0.75 | 0 / 0 |
| hard | 0.50 | 0 / 0 |

## Precision

- **Rate**: 1.00
- **Sample size**: 8
- **Automated**: Yes



## Calibration

| Confidence Range | Claims | Matched | Observed Precision | Bar |
|------------------|--------|---------|-------------------|-----|
| (0.0, 0.2] | 0 | 0 | N/A |  |
| (0.2, 0.4] | 0 | 0 | N/A |  |
| (0.4, 0.6] | 0 | 0 | N/A |  |
| (0.6, 0.8] | 3 | 3 | 1.00 | ████████████████████ |
| (0.8, 1.0] | 5 | 5 | 1.00 | ████████████████████ |

**Expected Calibration Error (ECE)**: 0.1750

## Risk Recall

| Planted Risk | Matched | Severity Match |
|--------------|---------|---------------|
| `risk_a01` | Yes | Yes |

## Fact Matches

| Fact ID | Strategy | Score | Matched Claim | Confidence |
|---------|----------|-------|---------------|------------|
| `fact_a01` | exact | 1.0 | Aria Vellinor is the founder and Managing Partner of Vellinor Capital | 0.92 |
| `fact_a02` | fuzzy | 100.0 | Aria Vellinor was born in Velmaris | 0.88 |
| `fact_a03` | fuzzy | 100.0 | Aria Vellinor holds a Master of Finance from the Velmaris Institute of Technology | 0.82 |
| `fact_a04` | exact | 1.0 | Vellinor Capital was founded in 2019 | 0.89 |
| `fact_a05` | fuzzy | 100.0 | Aria Vellinor serves on the board of the Velmaris Digital Commerce Association | 0.78 |
| `fact_a06` | fuzzy | 100.0 | Aria Vellinor was previously Chief Technology Officer at Meridian Fintech Solutions | 0.83 |
| `fact_a07` | fuzzy | 100.0 | Vellinor Capital led a Series B investment of 45 million Velmaris crowns in Nexara Systems | 0.80 |
| `fact_a08` | fuzzy | 0.0 | — | — |
| `fact_a09` | semantic | 0.0 | — | — |
| `fact_a10` | fuzzy | 100.0 | The Velmaris Financial Oversight Authority opened a preliminary inquiry into Vellinor Capital in March 2022 | 0.72 |
| `fact_a11` | semantic | 0.0 | — | — |
| `fact_a12` | fuzzy | 71.7 | Aria Vellinor was born in Velmaris | 0.88 |

## Cost Summary

| Metric | Value |
|--------|-------|
| Cost | $0.85 |
| Duration | 0.0s |
| Iterations | 1 |
| Search Calls | 6 |

## Success Criteria

| Criterion | Status |
|-----------|--------|
| High Confidence Precision | PASS |
| Easy Recall | PASS |
| Risk Recall | PASS |