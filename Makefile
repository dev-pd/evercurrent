# EverCurrent — developer ergonomics. Everything runs in docker. `make help`
# lists targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
API_RUN := $(COMPOSE) run --rm api
API_EXEC := $(COMPOSE) exec api
# Web lint/format/test run against the `web-dev` profile (builder stage image
# with full node_modules + source). `pnpm` is on PATH inside that image.
WEB_RUN := $(COMPOSE) --profile dev run --rm web-dev

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

.PHONY: build
build: ## Rebuild all images
	$(COMPOSE) build

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

# ----- Backend (everything inside containers) ---------------------------------

.PHONY: migrate
migrate: ## Apply Alembic migrations against the running stack
	$(API_EXEC) alembic upgrade head

.PHONY: migration
migration: ## Create a new Alembic migration. Usage: make migration name="add foo"
	@if [ -z "$(name)" ]; then echo "Usage: make migration name=\"<short description>\""; exit 1; fi
	$(API_EXEC) alembic revision --autogenerate -m "$(name)"

.PHONY: seed
seed: ## Full seed: project, users, channels, messages, docs
	$(API_EXEC) python -m evercurrent.ingestion.seeder --all

.PHONY: seed-base
seed-base: ## Seed only project + users + channels
	$(API_EXEC) python -m evercurrent.ingestion.seeder

.PHONY: reset
reset: ## Drop + recreate the schema + rerun the full seed
	$(API_EXEC) alembic downgrade base
	$(API_EXEC) alembic upgrade head
	$(API_EXEC) python -m evercurrent.ingestion.seeder --all

.PHONY: seed-messages
seed-messages: ## Load committed synthetic messages into the DB
	$(API_EXEC) python -m evercurrent.ingestion.seeder --load-messages

.PHONY: seed-docs
seed-docs: ## Load committed project docs into the DB
	$(API_EXEC) python -m evercurrent.ingestion.seeder --load-docs

.PHONY: ingest-docs
ingest-docs: ## Run RAG document ingestion (chunk + embed + index)
	$(API_EXEC) python -m evercurrent.rag.indexer --all

.PHONY: generate-digests
generate-digests: ## Generate digests for day=N (current phase). Usage: make generate-digests day=3
	@if [ -z "$(day)" ]; then echo "Usage: make generate-digests day=<N>"; exit 1; fi
	$(API_EXEC) python -m evercurrent.digest.generator --day $(day)

.PHONY: precompute-digests
precompute-digests: ## Pre-compute every (user, day, phase) digest. ~240 Sonnet calls, ~10-20 min.
	$(API_EXEC) python -m evercurrent.digest.generator --all

.PHONY: psql
psql: ## Open a psql shell against the running postgres container
	$(COMPOSE) exec postgres psql -U evercurrent -d evercurrent

.PHONY: shell-api
shell-api: ## Drop into a Python shell inside the api container
	$(API_EXEC) python

.PHONY: shell-bash
shell-bash: ## Drop into bash inside the api container
	$(API_EXEC) bash

# ----- Quality gates (inside containers) --------------------------------------

.PHONY: lint
lint: ## ruff + ty (api) and eslint + prettier check (web), all inside docker
	$(API_RUN) sh -c "ruff check && ty check"
	$(WEB_RUN) sh -c "pnpm lint && pnpm format:check && pnpm typecheck"

.PHONY: fmt
fmt: ## ruff format + ruff --fix (api) and prettier (web), inside docker
	$(API_RUN) sh -c "ruff format && ruff check --fix"
	$(WEB_RUN) sh -c "pnpm format"

.PHONY: test
test: ## Health/ready unit tests (api). Web has no traditional tests by policy.
	$(API_RUN) pytest tests/unit -v

.PHONY: eval
eval: ## Eval harness (RAG, scoring, digest, decisions)
	$(API_RUN) pytest tests/evals -v -s --no-cov
