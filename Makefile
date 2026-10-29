.PHONY: install test lint format typecheck check vectors vectors-check

install:
	uv sync --frozen

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

check: lint typecheck test

# Regenera los vectores de referencia (requiere JDK, Node 22 y cc).
vectors:
	tests/vectors/generate.sh

# Regenera en un directorio temporal y compara con los versionados.
vectors-check:
	tmp=$$(mktemp -d) && tests/vectors/generate.sh $$tmp && \
	uv run python tests/vectors/compare.py tests/vectors/data $$tmp
