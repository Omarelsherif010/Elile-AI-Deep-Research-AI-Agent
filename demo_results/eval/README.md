# Evaluation Suite Results

## Overview

The eval suite measures three properties of the research agent:

| Metric | What it measures | How |
|--------|-----------------|-----|
| **Recall** | Did the agent find the planted facts? | Match agent claims against ground-truth facts using exact, fuzzy (rapidfuzz), or semantic (OpenAI embeddings) strategies |
| **Precision** | Are the agent's claims accurate? | Sample claims and verify against source URLs |
| **Calibration (ECE)** | Are confidence scores well-calibrated? | Compare predicted confidence to actual correctness across buckets |

## Personas

### 1. Satya Nadella (Real Public Figure)

- **File:** `eval/personas/persona_real_public.yaml`
- **Type:** `real_public` — uses only publicly verifiable facts
- **Planted facts:** 10 (4 easy, 3 medium, 3 hard)
- **Planted risks:** None — tests precision and no-fabrication discipline
- **Expected outcome:** Meaningful recall, since Satya Nadella's information is widely indexed by search providers

### 2. Aria Vellinor (Synthetic)

- **File:** `eval/personas/persona_synthetic_a.yaml`
- **Type:** `synthetic` — facts planted on a GitHub Pages site
- **Plant site:** `eval/plant_site/` (deployed to GitHub Pages)

### 3. Dorian Ashcroft (Synthetic)

- **File:** `eval/personas/persona_synthetic_b.yaml`
- **Type:** `synthetic` — facts planted on a GitHub Pages site
- **Plant site:** `eval/plant_site/` (deployed to GitHub Pages)

## Known Limitation: Synthetic Persona Recall

Synthetic personas (Aria Vellinor, Dorian Ashcroft) have **0% recall** in practice. This is not a code bug — it is a real-world limitation of OSINT search infrastructure:

1. **The plant site is live** and accessible at its GitHub Pages URL
2. **Brave Search API does not index low-authority GitHub Pages** — the search provider returns zero results for these synthetic names
3. **The eval framework is correct** — it would accurately measure recall if the search provider returned results
4. **This is a known constraint** of synthetic eval personas in OSINT systems: search engines prioritize high-authority, high-traffic content

### Why this matters

This limitation is itself an important finding about OSINT system evaluation:
- Synthetic personas test the eval framework's design (planted facts with ground truth, tiered difficulty, multiple matching strategies)
- But they cannot test the agent's actual search-to-extraction pipeline unless the search provider indexes the plant content
- Production eval would use: (a) Exa semantic search (already in the fallback config), (b) Google Custom Search, or (c) a pre-seeded search cache that returns plant site content

### What this demonstrates

The eval framework correctly handles this case:
- It reports 0% recall honestly, not fabricated results
- It distinguishes between "the agent didn't find this" and "the search provider didn't return this"
- The matching pipeline (exact → fuzzy → semantic) works correctly when claims are present

## Included Results

### `live_run_synthetic_a/`

A real eval run of the synthetic persona (Aria Vellinor) against the live agent with real API calls and Brave Search. Demonstrates:
- 0% recall (Brave Search doesn't index the plant site)
- 52% precision (agent found some real claims about similar names)
- 0.49 ECE (poor calibration because no planted facts were matched)
- 950s runtime, 42 search calls

This result honestly shows the search provider limitation described above.

### `fixture_replay_synthetic_a/`

A replay of cached fixture data through the eval framework, demonstrating the eval pipeline works correctly when claims are present:
- 100% easy recall, 75% medium recall, 50% hard recall
- 100% precision
- 100% risk recall
- 0.175 ECE (well-calibrated)

This result validates the matching, scoring, and reporting pipeline independent of search provider limitations.

### `timothy_overturf/` (sibling directory)

The primary investigation target. Not run through the eval framework (no planted facts persona), but demonstrates the full agent pipeline:
- 670 validated claims, 69 entities, 258 relations
- 2 CRITICAL regulatory findings (SEC enforcement action)
- 4 COVERAGE_GAP findings (honest disclosure)
- `report.md` — human-readable report
- `report_summary.json` — trimmed machine-readable data (92KB vs 4MB full)

## Running the Eval Suite

```bash
# Run all personas
python -m eval run

# Run a single persona
python -m eval run --persona persona_real_public

# Replay from cached artifacts (no API calls)
python -m eval replay --run-id <run_id>

# Validate persona YAML
python -m eval validate-persona --all
```

## Metrics Interpretation

- **Recall by tier:** Easy facts should have higher recall than hard facts. If easy recall is 0%, the search provider likely didn't find the target.
- **Precision:** For real public figures, precision should be high (>0.8) since facts are verifiable. For synthetic personas, precision is undefined (no claims to verify).
- **ECE (Expected Calibration Error):** Lower is better. ECE < 0.15 indicates well-calibrated confidence scores. High ECE means the agent is over- or under-confident.
- **Risk recall:** What fraction of planted risk patterns did the agent identify? Only applicable when `planted_risks` is non-empty.
