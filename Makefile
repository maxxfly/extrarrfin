# Tool binaries: use the local venv when it exists, otherwise fall back to
# whatever is on PATH (CI installs into the system interpreter).
BIN := $(if $(wildcard .venv/bin),.venv/bin/,)
MYPY := $(BIN)mypy
RUFF := $(BIN)ruff
PYTEST := $(BIN)pytest

.PHONY: help install lint type check format clean test pytest test-unit test-themerrdb ci

help:
	@echo "Available targets:"
	@echo "  install    - Install dependencies"
	@echo "  lint       - Run ruff linter"
	@echo "  type       - Run mypy type checker"
	@echo "  check      - Run both lint and type checks"
	@echo "  format     - Format code with ruff"
	@echo "  clean      - Remove Python cache files"
	@echo "  test       - Run all checks (lint + type)"
	@echo "  test-unit  - Run offline pytest suite (no internet needed)"
	@echo "  ci         - Run what GitHub Actions runs (type + offline tests, no network)"
	@echo "  pytest     - Run integration tests (requires internet)"
	@echo "  test-themerrdb - Run ThemerrDB integration tests (requires internet)"

install:
	pip install -r requirements.txt

lint:
	@echo "Running ruff..."
	$(RUFF) check extrarrfin/

type:
	@echo "Running mypy..."
	$(MYPY) extrarrfin/ tests/ conftest.py --show-error-codes
	# The entrypoint is checked in a separate invocation: mypy refuses to map
	# extrarrfin.py and extrarrfin/__init__.py to the same module name at once.
	$(MYPY) extrarrfin.py --show-error-codes

check: lint type
	@echo "All checks passed!"

format:
	@echo "Formatting with ruff..."
	$(RUFF) format extrarrfin/
	$(RUFF) check --fix extrarrfin/

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

test: check
	@echo "Tests completed!"

pytest:
	@echo "Running pytest integration tests..."
	$(PYTEST) tests/ -v -m integration

test-unit:
	@echo "Running offline unit tests (no network)..."
	$(PYTEST) tests/ -v -m "not integration"

test-themerrdb:
	@echo "Running ThemerrDB tests (offline + real download, requires internet)..."
	$(PYTEST) tests/test_themerrdb.py tests/test_theme_no_fallback.py tests/test_theme_no_fallback_cli.py -v
	$(PYTEST) tests/test_themerrdb_download.py -v -m integration

# What GitHub Actions runs: offline checks only, no network, no lint gate.
ci: type test-unit
	@echo "CI checks passed!"
