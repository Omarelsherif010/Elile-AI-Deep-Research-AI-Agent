# Quickstart: Deep Research AI Agent

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for: Anthropic (Claude), OpenAI (GPT-5.4 Mini), Google AI (Gemini)
- API key for: Brave Search
- Optional: Neo4j Aura account (free tier), Exa API key, Firecrawl API key, LangSmith API key

## Setup

```bash
# Clone and enter the repo
git clone <repo-url>
cd deep-research-agent

# Install dependencies
make install
# (equivalent to: uv sync)

# Copy environment template and fill in your API keys
cp .env.example .env
# Edit .env with your keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
#   GOOGLE_API_KEY=AI...
#   BRAVE_API_KEY=BSA...

# Verify setup
make lint
make test
```

## First Run

```bash
# Run against a well-known public figure
make run TARGET="Elon Musk"

# Or with more context
python -m research_agent run \
  --target "Elon Musk" \
  --role "CEO" \
  --org "Tesla, SpaceX" \
  --context "Focus on regulatory and financial risk" \
  --output runs/demo-elon
```

The run produces five files in the output directory:
- `report.md` — Read this first. Human-readable risk report.
- `report.json` — Same data, machine-readable.
- `graph_export.json` — Identity graph (nodes + edges).
- `audit.json` — Per-node execution log (engineer-only).
- `checkpoint.sqlite` — Resumable checkpoint.

## Run the Eval Suite

```bash
# Run all three eval personas
make eval

# Run a specific persona
python -m research_agent eval --persona persona_synthetic_a
```

## Available Commands

```bash
make install        # Install dependencies via uv
make lint           # Check code with ruff
make test           # Run unit tests (mocked)
make test-live      # Run integration tests (real APIs)
make run TARGET="X" # Run against a target
make eval           # Run eval suite (3 personas)
make demo           # Launch Streamlit demo (if available)
make clean          # Remove build artifacts
```

## Project Structure Overview

- `src/research_agent/` — Main package (nodes, tools, schemas)
- `prompts/` — Runtime LLM prompts (version-controlled markdown)
- `eval/` — Evaluation personas and metrics
- `tests/` — Unit and integration tests
- `runs/` — Per-run output artifacts (gitignored)
