# Authoring Guide: Adding a New Eval Persona

This guide explains how to add a new persona to the eval suite. A new engineer should be able to complete this in under one hour.

## Prerequisites

- Python 3.11+ installed
- Project installed: `make install`
- Basic understanding of YAML syntax

## Step 1: Choose a Persona Type

### Synthetic
- Use for controlled evaluation where you know all ground-truth facts.
- Requires HTML plant site pages so the agent can discover facts via web search.
- All names, companies, and events must be clearly fictional.

### Real Public
- Use for evaluating the agent against a real public figure.
- Facts must be sourced from tier-1 or tier-2 public sources with URLs.
- No planted risks (tests precision and no-fabrication discipline).

## Step 2: Copy the Template

```bash
cp eval/personas/_template.yaml eval/personas/persona_my_new.yaml
```

## Step 3: Fill in the YAML

### Required Fields

| Field | Guidance |
|-------|----------|
| `id` | Pattern: `persona_[a-z_]+`. Must be unique. |
| `target_name` | Full name of the person. Max 200 chars. |
| `target_context` | Disambiguating context (location, role, industry). |
| `persona_type` | `synthetic` or `real_public`. |
| `description` | One-paragraph profile. |
| `ethical_notes` | Explain fictional status or source ethics. |
| `plant_site_root` | Required for `synthetic`. Path to HTML directory relative to repo root. |

### Planted Facts

Each fact needs:

| Field | Guidance |
|-------|----------|
| `id` | Pattern: `fact_[a-z]\d{2}` (e.g., `fact_m01`). |
| `statement` | The exact fact as a declarative sentence. Max 500 chars. |
| `difficulty` | `easy`, `medium`, or `hard` (see definitions below). |
| `expected_dimension` | One of: `biographical`, `professional_history`, `financial_connections`, `network`, `public_statements`, `risk_surface`. |
| `fact_type` | One of: `biographical`, `role`, `financial`, `network`, `statement`, `risk`. |
| `match_strategy` | `exact`, `fuzzy`, or `semantic`. Default: `fuzzy`. |
| `match_threshold` | For `fuzzy`: [0, 100]. For `semantic`: [0.0, 1.0]. Default: 80.0. |
| `notes` | Explain why this tier was chosen. |
| `source_urls` | At least one URL. For synthetic, use plant site page URLs. |

### Difficulty Tier Definitions

| Tier | Definition | Example Location |
|------|-----------|------------------|
| **easy** | Visible in a headline, page title, or opening paragraph. | index.html, biography page top. |
| **medium** | Requires reading the article body; not in the opening. | career timeline, portfolio details. |
| **hard** | Requires cross-referencing multiple pages; likely paraphrased. | connecting statements across press + filings. |

### Match Strategy Guidance

| Strategy | When to Use | Example |
|----------|-------------|---------|
| **exact** | Highly structured facts with little variation. | "Founded Vellinor Capital in 2019" |
| **fuzzy** | Facts that may appear with extra context words. | "serves on the board of X" vs "board member of X" |
| **semantic** | Facts likely to be paraphrased by the agent. | "advocated for transparent AI governance" |

### Planted Risks (Optional)

Each risk needs:

| Field | Guidance |
|-------|----------|
| `id` | Pattern: `risk_[a-z]\d{2}`. |
| `risk_category` | `REGULATORY`, `REPUTATIONAL`, `NETWORK`, `FINANCIAL`, `INCONSISTENCY`, `COVERAGE_GAP`, `OTHER`. |
| `expected_severity` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `description` | Clear description of the risk. |
| `evidence_source_urls` | URLs supporting the risk. |

## Step 4: Validate the YAML

```bash
python -m eval validate-persona --persona persona_my_new
```

Fix any validation errors before proceeding.

## Step 5: Add Plant Site Pages (Synthetic Only)

Create HTML pages under `eval/plant_site/{persona-id}/`:

```bash
mkdir -p eval/plant_site/my-persona
```

### Page Structure Guidelines

- Each page must include the shared CSS: `<link rel="stylesheet" href="../_shared/style.css">`
- Each page must have a disclaimer banner at the top.
- Use semantic HTML (`<article>`, `<header>`, `<time>`, `<section>`).
- Include nav links to other pages.
- Write facts in natural prose, not as data dumps.

### Minimum Pages

| Page | Purpose |
|------|---------|
| `index.html` | Biography with easy-tier facts. |
| `career.html` | Career timeline with medium-tier facts. |
| `portfolio.html` | Investments / roles with medium/hard facts. |

### Example HTML Skeleton

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Person Name — Page Title</title>
  <link rel="stylesheet" href="../_shared/style.css">
</head>
<body>
<div class="disclaimer"><strong>Fictional persona for AI evaluation only.</strong></div>
<header>
  <h1>Person Name</h1>
  <nav>
    <a href="index.html">Biography</a>
    <a href="career.html">Career</a>
  </nav>
</header>
<article>
  <h2>Section Title</h2>
  <p>Natural prose containing a planted fact, such as:
     Person Name founded ExampleCo in 2025.</p>
</article>
<footer>
  <p>This page is part of a fictional persona created for AI evaluation.</p>
</footer>
</body>
</html>
```

## Step 6: Update the Sitemap

Add new pages to `eval/plant_site/sitemap.xml`.

## Step 7: Run Eval for a Single Persona

```bash
make eval-one PERSONA=persona_my_new
```

Or directly:

```bash
python -m eval run --persona persona_my_new
```

## Step 8: Review the Report

Open `eval/reports/{run_id}/{persona_id}.md` and check:
- Recall by tier is reasonable for the difficulty you assigned.
- Fact matches show the correct strategy and scores.
- No validation errors in the persona YAML.

## Checklist for New Persona Authors

- [ ] `id` follows the `persona_[a-z_]+` pattern.
- [ ] All `fact_*` IDs follow `fact_[a-z]\d{2}`.
- [ ] All `risk_*` IDs follow `risk_[a-z]\d{2}` (if risks present).
- [ ] At least one fact per tier (easy, medium, hard) for synthetic personas.
- [ ] All source URLs are non-empty and valid.
- [ ] Synthetic persona has `plant_site_root` set.
- [ ] Plant site pages include disclaimer and nav links.
- [ ] Facts appear in natural prose, not as lists.
- [ ] Sitemap updated.
- [ ] `validate-persona` passes.
- [ ] Single-persona eval runs without errors.
