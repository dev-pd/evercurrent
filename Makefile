# EverCurrent — developer ergonomics. `make help` lists targets.
.DEFAULT_GOAL := help
SHELL := /bin/bash

API := apps/api
WEB := apps/web
COMPOSE := docker compose

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

# ----- Docker compose ---------------------------------------------------------

.PHONY: up
up: ## Start the full stack (postgres + redis + api + worker + web + nginx)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack (preserves volumes)
	$(COMPOSE) down

.PHONY: down-v
down-v: ## Stop the stack AND wipe volumes (postgres + redis)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

# ----- Backend ----------------------------------------------------------------

.PHONY: api
api: ## Run the API outside docker (fastapi dev with hot reload)
	cd $(API) && uv run fastapi dev src/evercurrent/main.py

.PHONY: migrate
migrate: ## Apply Alembic migrations against the running stack
	$(COMPOSE) exec api alembic upgrade head

.PHONY: migration
migration: ## Create a new Alembic migration. Usage: make migration name="add foo table"
	@if [ -z "$(name)" ]; then echo "Usage: make migration name=\"<short description>\""; exit 1; fi
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(name)"

.PHONY: seed
seed: ## Run the seed script inside the api container
	$(COMPOSE) exec api python -m evercurrent.ingestion.seeder

.PHONY: ingest-docs
ingest-docs: ## Run RAG document ingestion
	$(COMPOSE) exec api python -m evercurrent.rag.indexer --all

.PHONY: generate-digests
generate-digests: ## Generate digests for day=N. Usage: make generate-digests day=3
	@if [ -z "$(day)" ]; then echo "Usage: make generate-digests day=<N>"; exit 1; fi
	$(COMPOSE) exec api python -m evercurrent.digest.cli --day $(day)

# ----- Frontend ---------------------------------------------------------------

.PHONY: web
web: ## Run the Next.js dev server outside docker
	cd $(WEB) && pnpm dev

# ----- Quality gates ----------------------------------------------------------

.PHONY: lint
lint: ## ruff + ty (api) and eslint + prettier check (web)
	cd $(API) && uv run ruff check && uv run ty check
	cd $(WEB) && pnpm lint && pnpm format:check && pnpm typecheck

.PHONY: fmt
fmt: ## ruff format (api) + prettier write (web)
	cd $(API) && uv run ruff format && uv run ruff check --fix
	cd $(WEB) && pnpm format

.PHONY: test
test: ## Health/ready unit tests (api). Web has no traditional tests by policy.
	cd $(API) && uv run pytest tests/unit -v

.PHONY: eval
eval: ## Eval harness (RAG, scoring, digest, decisions)
	cd $(API) && uv run pytest tests/evals -v -s --no-cov

# ----- Pre-commit -------------------------------------------------------------

.PHONY: pre-commit
pre-commit: ## Install + run pre-commit hooks across all files
	pre-commit install
	pre-commit run --all-files
