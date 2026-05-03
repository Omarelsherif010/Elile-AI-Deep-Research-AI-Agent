---
description: Run the eval suite against all three personas and report metrics.
---

You are running the project's evaluation suite. The user wants to measure recall, precision, and confidence calibration on the three eval personas.

## Your steps

1. Confirm the eval suite exists at `eval/runner.py`. If not, surface that the suite isn't built yet and stop.

2. Confirm the three persona files exist at `eval/personas/persona_synthetic_a.yaml`, `eval/personas/persona_synthetic_b.yaml`, `eval/personas/persona_real_public.yaml`. If any are missing, surface that and stop.

3. Check that `.env` is present and contains the required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `BRAVE_API_KEY`, `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `LANGSMITH_API_KEY`. If any are missing, list which ones and stop.

4. Estimate cost. Each persona consumes roughly $0.50–$2.00 in API calls depending on iterations. Confirm with the user before proceeding if running fresh (i.e., not from cache).

5. Run `make eval` and capture stdout/stderr.

6. Parse the output and report:
   - Recall per persona (easy / medium / hard tiers)
   - Precision per persona
   - Confidence calibration — bucket claims by confidence band, report observed precision per band
   - Risk recall per persona
   - Total cost incurred
   - Total time elapsed

7. Compare against the success criteria in `specs/001-deep-research-agent/spec.md`:
   - Recall ≥ 70% easy, ≥ 40% hard
   - Precision ≥ 90%
   - High-confidence (>0.8) precision ≥ 95%
   - Risk recall ≥ 80%

8. For each criterion that fails, suggest the most likely cause based on which node's output looks weakest in the audit logs at `runs/`.

## Constraints

- Do not modify the eval personas or planted facts during a run. The eval set is the contract.
- Do not modify prompts during a run.
- If a run fails partway, capture which persona failed and at what node, and surface that — do not silently retry.
- The eval suite hits live APIs; respect rate limits. If rate-limited, recommend `make eval` with `--cache-only` (if implemented) or wait and retry.