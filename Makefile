.PHONY: help install lint type check format clean test

help:
	@echo "Available targets:"
	@echo "  install    - Install dependencies"
	@echo "  lint       - Run ruff linter"
	@echo "  type       - Run mypy type checker"
	@echo "  check      - Run both lint and type checks"
	@echo "  format     - Format code with ruff"
	@echo "  clean      - Remove Python cache files"
	@echo "  test       - Run all checks (lint + type)"

install:
	pip install -r requirements.txt

lint:
	@echo "Running ruff..."
	ruff check extrarrfin/

type:
	@echo "Running mypy..."
	mypy extrarrfin/ --python-version 3.10 --show-error-codes

check: lint type
	@echo "All checks passed!"

format:
	@echo "Formatting with ruff..."
	ruff format extrarrfin/
	ruff check --fix extrarrfin/

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

test: check
	@echo "Tests completed!"
