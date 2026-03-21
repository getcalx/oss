.PHONY: fmt lint typecheck test check

fmt:
	ruff format src/ tests/
	ruff check --fix src/ tests/

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

test:
	pytest

check: fmt lint typecheck test
