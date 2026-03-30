.DEFAULT_GOAL := help
.PHONY: install lint format typecheck test test-cov security docker-build docker-up docker-down run clean pre-commit help

PYTHON   ?= python
PIP      ?= pip
PYTEST   ?= pytest
RUFF     ?= ruff
MYPY     ?= mypy
BANDIT   ?= bandit
UVICORN  ?= uvicorn

SRC_DIR  := src/iotguard
TEST_DIR := tests

# ---------------------------------------------------------------------------
# Development setup
# ---------------------------------------------------------------------------

install:  ## Install the project with all extras in editable mode
	$(PIP) install -e ".[dev,test]"

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:  ## Run linter checks (ruff)
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)

format:  ## Auto-format code (ruff)
	$(RUFF) format $(SRC_DIR) $(TEST_DIR)
	$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR)

typecheck:  ## Run static type checking (mypy)
	$(MYPY) $(SRC_DIR) --ignore-missing-imports

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test:  ## Run the test suite
	$(PYTEST) $(TEST_DIR) -v

test-cov:  ## Run tests with coverage report
	$(PYTEST) $(TEST_DIR) -v \
		--cov=iotguard \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

security:  ## Run security scans (bandit + pip-audit)
	$(BANDIT) -r $(SRC_DIR) -c pyproject.toml || true
	$(PIP) install pip-audit && pip-audit --strict || true

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-build:  ## Build the Docker image
	docker build -t iotguard:latest -f docker/Dockerfile .

docker-up:  ## Start the full stack with docker compose
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:  ## Stop the docker compose stack
	docker compose -f docker/docker-compose.yml down -v

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

run:  ## Start the development server
	$(UVICORN) iotguard.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean:  ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .mypy_cache .ruff_cache .pytest_cache htmlcov
	rm -f coverage.xml junit.xml bandit-report.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

pre-commit:  ## Install and run pre-commit hooks
	pre-commit install
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
