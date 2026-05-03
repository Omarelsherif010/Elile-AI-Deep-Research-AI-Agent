---
description: Run a fast smoke test of the agent end-to-end against a synthetic persona with minimal budget.
---

You are running a smoke test. Goal: verify the agent's full pipeline executes end-to-end without errors. This is NOT a quality test — recall and precision will be poor with reduced budgets.

## Your steps

1. Confirm the agent is buildable: run `make lint && make test`. If either fails, surface the failures and stop. Smoke runs against a broken codebase waste API budget.

2. Set smoke-test budget overrides via env vars:
   - `SMOKE_TEST=1`
   - `MAX_ITERATIONS=2`
   - `MAX_SEARCH_CALLS=10`
   - `MAX_DOLLARS=0.50`

3. Pick the synthetic persona with the smallest planted fact set: `eval/personas/persona_synthetic_a.yaml`. Read its `target_name` and `target_context` fields.

4. Run the agent:
   ```
   python -m research_agent run --target "<target_name>" --context "<target_context>" --output runs/smoke_$(date +%s)
   ```

5. Verify the run produced all four expected outputs:
   - `runs/smoke_*/report.md`
   - `runs/smoke_*/report.json`
   - `runs/smoke_*/audit.json`
   - Neo4j graph populated (query `MATCH (p:Person) RETURN p` should return ≥ 1 row)

6. Verify each node ran at least once by inspecting `audit.json`:
   - planner, search_orchestrator, extractor, validator, reflector, graph_builder, risk_analyzer, reporter

7. Surface a smoke-test summary:
   - PASS / FAIL for each verification step
   - Total iterations actually run
   - Total cost incurred
   - First 3 lines of the generated report
   - Number of entities, relations, claims, risk flags
   - Any errors or warnings in audit.json

8. If FAIL: identify the first node that did not run or the first error. Suggest the likely cause. Do not propose code changes — that's a separate task.

## Constraints

- Smoke runs are for plumbing verification, not quality. Do not interpret low recall as a bug.
- Cost cap is hard. If the run reports `BudgetExceeded` before the reporter, that's expected for smoke; verify graceful termination still produced a report (even a "budget exhausted" note).
- Do not modify prompts, weights, or schemas during a smoke run.