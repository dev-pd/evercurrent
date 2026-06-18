# EverCurrent — developer ergonomics. Everything runs in docker.
# `make help` lists targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
API_RUN := $(COMPOSE) run --rm api
API_EXEC := $(COMPOSE) exec api
WEB_RUN := $(COMPOSE) --profile dev run --rm web-dev

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

# ----- Docker compose --------------------------------------------------------

.PHONY: up
up: ## Start stack (postgres + redis + api + worker + beat + web + nginx)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop stack (volumes preserved)
	$(COMPOSE) down

.PHONY: down-v
down-v: ## Stop stack AND wipe volumes
	$(COMPOSE) down -v

.PHONY: build
build: ## Rebuild images
	$(COMPOSE) build

.PHONY: logs
logs: ## Tail logs (all services)
	$(COMPOSE) logs -f

.PHONY: logs-api
logs-api: ## Tail api logs only
	$(COMPOSE) logs -f api

.PHONY: logs-worker
logs-worker: ## Tail worker logs only
	$(COMPOSE) logs -f worker

.PHONY: ps
ps: ## Container status
	$(COMPOSE) ps

# ----- Database --------------------------------------------------------------

.PHONY: migrate
migrate: ## Apply Alembic migrations
	$(API_EXEC) alembic upgrade head

.PHONY: migration
migration: ## Create new migration. Usage: make migration name="add foo"
	@if [ -z "$(name)" ]; then echo "Usage: make migration name=\"<short description>\""; exit 1; fi
	$(API_EXEC) alembic revision --autogenerate -m "$(name)"

.PHONY: check-models
check-models: ## Fail if any ORM model column is absent from its migrated table (drift)
	$(API_EXEC) python -m evercurrent.db.schema_check

.PHONY: psql
psql: ## Open psql against the dev DB
	$(COMPOSE) exec postgres psql -U evercurrent -d evercurrent

# ----- Shells ----------------------------------------------------------------

.PHONY: shell-api
shell-api: ## Python shell inside api container
	$(API_EXEC) python

.PHONY: shell-bash
shell-bash: ## Bash inside api container
	$(API_EXEC) bash

# ----- Quality gates ---------------------------------------------------------

.PHONY: lint
lint: ## ruff + ty (api) and eslint + prettier + tsc (web)
	$(API_RUN) sh -c "ruff check && ty check"
	$(WEB_RUN) sh -c "pnpm lint && pnpm format:check && pnpm typecheck"

.PHONY: fmt
fmt: ## ruff format + auto-fix (api) and prettier (web)
	$(API_RUN) sh -c "ruff format && ruff check --fix"
	$(WEB_RUN) sh -c "pnpm format"

# ----- Tests -----------------------------------------------------------------

.PHONY: test
test: test-unit ## Default: unit tests (fast)

.PHONY: test-unit
test-unit: ## Unit tests (api, no external services)
	$(API_RUN) pytest tests/unit -v

.PHONY: test-integration
test-integration: ## Integration tests (api, testcontainers Postgres + Redis)
	$(API_RUN) pytest tests/integration -v

.PHONY: test-web
test-web: ## Web unit + component tests (vitest)
	$(WEB_RUN) pnpm test

.PHONY: e2e
e2e: ## Playwright E2E (needs the stack running: make up first)
	$(WEB_RUN) pnpm e2e

.PHONY: eval
eval: ## Eval harness: router + scoring + rag + digest
	$(API_RUN) pytest tests/evals -v -s --no-cov

.PHONY: eval-router
eval-router: ## Router eval only (ANTHROPIC_API_KEY required)
	$(API_RUN) pytest tests/evals/eval_router.py -v -s --no-cov

.PHONY: eval-scoring
eval-scoring: ## Scoring eval only (no API keys needed)
	$(API_RUN) pytest tests/evals/eval_scoring.py -v -s --no-cov

.PHONY: eval-rag
eval-rag: ## RAG eval only (VOYAGE_API_KEY required; testcontainers Postgres)
	$(API_RUN) pytest tests/evals/eval_rag.py -v -s --no-cov

.PHONY: eval-digest
eval-digest: ## Digest LLM-as-judge eval only (ANTHROPIC_API_KEY required)
	$(API_RUN) pytest tests/evals/eval_digest.py -v -s --no-cov

# ----- Dev utilities ---------------------------------------------------------

.PHONY: ngrok
ngrok: ## Expose port 8000 publicly for Slack webhooks (needs `ngrok` on PATH)
	@command -v ngrok >/dev/null 2>&1 || { echo "Install ngrok: brew install ngrok/ngrok/ngrok"; exit 1; }
	ngrok http 8000

# ----- Monitoring (opt-in profile) -------------------------------------------

.PHONY: up-monitor
up-monitor: ## Start stack + monitoring (prometheus + loki + promtail + grafana)
	$(COMPOSE) --profile monitor up -d --build

.PHONY: monitor
monitor: ## Open Grafana in browser
	@open http://localhost:3030 || xdg-open http://localhost:3030 || echo "Visit http://localhost:3030"

.PHONY: logs-pretty
logs-pretty: ## Tail api logs and pretty-print structlog JSON
	@command -v jq >/dev/null 2>&1 || { echo "Install jq: brew install jq"; exit 1; }
	$(COMPOSE) logs -f api worker beat | grep --line-buffered -E '^\S+\s+\|' | sed -u 's/^[^|]*| //' | jq -r 'select(.event != null) | "\(.timestamp // "") \(.level // "info" | ascii_upcase | .[0:4]) \(.event) \(. | del(.timestamp, .level, .event) | to_entries | map("\(.key)=\(.value)") | join(" "))"' 2>/dev/null

# ----- Demo / load -----------------------------------------------------------

.PHONY: demo-chatter
demo-chatter: ## Post one persona-chatter batch to Slack now (personas -> Slack -> webhook -> pipeline). Needs SLACK_DEMO_BOT_TOKEN in .env.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && uv run python -m evercurrent.scripts.demo_chatter

.PHONY: webhook
webhook: ## Post 10 live messages AS YOUR USER (xoxp) -> webhook -> pipeline (demo). Needs SLACK_USER_TOKEN. Vars: CHANNEL, COUNT, INTERVAL.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && \
		CHATTER_CHANNEL=$${CHANNEL:-mech-design} CHATTER_COUNT=$${COUNT:-10} CHATTER_INTERVAL=$${INTERVAL:-2} \
		uv run python -m evercurrent.scripts.user_chatter

.PHONY: webhook-resolve
webhook-resolve: ## Demo step 2: post resolving + follow-up replies into open-signal threads -> webhook -> auto-resolution (live). Needs SLACK_DEMO_BOT_TOKEN. Vars: RESOLVE, CONTEXT.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && \
		SIM_RESOLVE_COUNT=$${RESOLVE:-2} SIM_CONTEXT_COUNT=$${CONTEXT:-2} \
		uv run python -m evercurrent.scripts.resolve_chatter

# ----- Demo runbook (see prep/DEMO_PLAN.md) ---------------------------------

.PHONY: wipe
wipe: ## Clean Slack — bot AND user messages. Needs SLACK_DEMO_BOT_TOKEN + SLACK_USER_TOKEN in .env.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && uv run python -m evercurrent.scripts.slack_wipe

.PHONY: bot-msgs
bot-msgs: ## Post ~30 persona/bot messages to Slack (seed threads). Needs SLACK_DEMO_BOT_TOKEN. Vars: COUNT.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && \
		BOT_MSGS_COUNT=$${COUNT:-30} uv run python -m evercurrent.scripts.demo_chatter

.PHONY: user-msgs
user-msgs: ## Post 5 messages AS the Prasad user (xoxp) -> webhook -> pipeline. Needs SLACK_USER_TOKEN. Vars: CHANNEL, COUNT, INTERVAL.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && \
		CHATTER_CHANNEL=$${CHANNEL:-mech-design} CHATTER_COUNT=$${COUNT:-5} CHATTER_INTERVAL=$${INTERVAL:-2} \
		uv run python -m evercurrent.scripts.user_chatter

.PHONY: resolve-msgs
resolve-msgs: ## Post resolving replies into ~15 open-signal threads -> webhook -> auto-resolution. Needs SLACK_DEMO_BOT_TOKEN. Vars: RESOLVE, CONTEXT.
	@set -a; [ -f .env ] && . ./.env; set +a; cd apps/api && \
		SIM_RESOLVE_COUNT=$${RESOLVE:-15} SIM_CONTEXT_COUNT=$${CONTEXT:-0} \
		uv run python -m evercurrent.scripts.resolve_chatter

.PHONY: prune
prune: ## DESTRUCTIVE: nuke containers + volumes + dangling images for this project
	$(COMPOSE) --profile dev --profile monitor down -v --remove-orphans
	docker system prune -f
	@echo "Pruned. Run 'make up' or 'make up-monitor' to start fresh."

.PHONY: install-hooks
install-hooks: ## Install pre-commit git hooks
	pre-commit install

.PHONY: clean
clean: ## Remove caches + node_modules + .next + uv envs (NUKE)
	rm -rf apps/web/node_modules apps/web/.next apps/web/.vitest apps/api/.venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
