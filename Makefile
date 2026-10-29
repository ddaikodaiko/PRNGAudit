.PHONY: install test test-slow lint format typecheck check vectors vectors-check experiments

install:
	uv sync --frozen

test:
	uv run pytest

# Pruebas lentas (p. ej. untemper sobre los 2³² valores, ~4 min).
test-slow:
	uv run pytest -m slow

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

# Ejecuta todos los experimentos; resultados en experiments/out/.
experiments:
	@for f in experiments/e*.py; do echo "== $$f"; uv run python $$f || exit 1; done
