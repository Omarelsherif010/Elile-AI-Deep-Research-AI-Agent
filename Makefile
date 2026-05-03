.PHONY: install lint test test-live run eval eval-replay eval-one validate-personas deploy-plant-site demo clean

install:
	uv sync --extra dev

lint:
	uv run ruff check src/ tests/ eval/
	uv run ruff format --check src/ tests/ eval/

test:
	uv run pytest tests/unit/ tests/integration/ -x

test-live:
	uv run pytest tests/ --live -x

run:
	uv run python -m research_agent run --target "$(TARGET)"

eval:
	uv run python -m eval run $(ARGS)

eval-replay:
	uv run python -m eval replay --run-id $(RUN_ID) $(ARGS)

eval-one:
	uv run python -m eval run --persona $(PERSONA)

validate-personas:
	uv run python -m eval validate-persona --all

deploy-plant-site:
	git subtree push --prefix eval/plant_site origin gh-pages

demo:
	uv run streamlit run streamlit_app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -rf .ruff_cache .pytest_cache dist build; \
	echo "Cleaned."
