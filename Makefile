.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= uv
PNPM ?= pnpm
COMPOSE ?= docker compose -f infra/docker/docker-compose.yml

.PHONY: help
help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	     /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---------- Bootstrap ----------

.PHONY: install
install:  ## Install Python + Node deps via uv and pnpm.
	$(UV) sync --all-packages
	@if [ -f package.json ]; then $(PNPM) install; fi

.PHONY: hooks
hooks:  ## Install pre-commit hooks.
	$(UV) run pre-commit install

# ---------- Dev stack ----------

.PHONY: dev
dev:  ## Bring up the local stack (Postgres + Redis + MinIO + API + Web).
	$(COMPOSE) up --build -d
	@echo "API:     http://localhost:8000/healthz"
	@echo "Web:     http://localhost:3000"
	@echo "MinIO:   http://localhost:9001 (admin: minioadmin / minioadmin)"
	@echo "Logs:    make logs"

.PHONY: down
down:  ## Stop the local stack.
	$(COMPOSE) down

.PHONY: logs
logs:  ## Tail logs from the local stack.
	$(COMPOSE) logs -f --tail=100

.PHONY: api
api:  ## Run the API directly with uvicorn (no docker).
	$(UV) run uvicorn aqao_api.main:app --reload --host 0.0.0.0 --port 8000

# ---------- Quality ----------

.PHONY: lint
lint:  ## Run ruff + eslint.
	$(UV) run ruff check .
	@if [ -f package.json ]; then $(PNPM) -r --if-present lint; fi

.PHONY: format
format:  ## Format code (ruff + prettier).
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	@if [ -f package.json ]; then $(PNPM) -r --if-present format; fi

.PHONY: typecheck
typecheck:  ## mypy strict + tsc.
	$(UV) run mypy -p aqao_api -p aqao_agents -p aqao_eval -p aqao_redaction -p aqao_tools
	@if [ -f package.json ]; then $(PNPM) -r --if-present typecheck; fi

# ---------- Tests ----------

.PHONY: test
test:  ## Run all tests (unit + integration).
	$(UV) run pytest

.PHONY: test-unit
test-unit:  ## Run unit tests only.
	$(UV) run pytest -m "not integration"

.PHONY: test-int
test-int:  ## Run integration tests (requires `make dev`).
	$(UV) run pytest -m integration

# ---------- Data plane ----------

.PHONY: migrate
migrate:  ## Apply Alembic migrations.
	$(UV) run alembic -c apps/api/alembic.ini upgrade head

.PHONY: seed
seed:  ## Seed a demo workspace.
	$(UV) run python scripts/seed.py

# ---------- Evaluation ----------

.PHONY: eval
eval:  ## Run the agent evaluation harness.
	$(UV) run python -m aqao_eval.cli run --baseline=docs/eval/baseline.json

.PHONY: eval-promote
eval-promote:  ## Promote feedback regression cases into the scored datasets.
	$(UV) run python -m aqao_eval.cli promote-feedback --datasets=packages/eval/datasets

# ---------- Browsers ----------

.PHONY: playwright-install
playwright-install:  ## Install Playwright browsers.
	$(UV) run playwright install --with-deps chromium

# ---------- Cleanup ----------

.PHONY: clean
clean:  ## Remove caches and build artifacts.
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov coverage.xml dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
