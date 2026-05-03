.PHONY: install lint test test-live run eval demo clean

install:
	uv sync --extra dev

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

test:
	uv run pytest tests/unit/ tests/integration/ -x

test-live:
	uv run pytest tests/ --live -x

run:
	uv run python -m research_agent run --target "$(TARGET)"

eval:
	uv run python -m research_agent eval

demo:
	uv run streamlit run streamlit_app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -rf .ruff_cache .pytest_cache dist build; \
	echo "Cleaned."
