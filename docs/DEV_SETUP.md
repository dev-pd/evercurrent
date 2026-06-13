# Developer setup

First-time setup. Should take ~10 minutes.

## Prerequisites

- Docker + docker-compose
- Node 25 + pnpm 11 (only for `pnpm install` outside containers if you
  want IDE autocomplete; the runtime lives in docker)
- Python 3.13 + uv (same — IDE only; docker runs the real thing)
- ngrok (for Slack webhooks during dev)

## 1. Clone + env

```bash
git clone <repo>
cd evercurrent
cp .env.example .env
```

Open `.env` and fill in keys as you need them per phase. The bare
minimum to boot the stack is the docker-compose defaults — they're
pre-filled.

## 2. Start the stack

```bash
make up         # builds + starts postgres, redis, api, worker, beat, web, nginx
make migrate    # applies Alembic schema
```

Wait ~60s. Check:

- API health: `curl http://localhost:8080/api/v1/health` → `{"status":"ok"}`
- Web: open `http://localhost:8080` → placeholder page (Phase 9 builds dashboard)

## 3. Run tests

```bash
make test            # unit tests inside the api container
make test-integration   # integration tests (testcontainers spawns its own Postgres + Redis)
make lint            # ruff + ty + eslint + prettier + tsc
```

Initial run pulls test container images (~30s); subsequent runs cache.

## 4. Pre-commit hook

```bash
pre-commit install
```

Runs ruff + ty + eslint + prettier on staged files before every commit.
First run may take ~30s installing hook envs.

## 5. ngrok for webhooks (only needed for Slack)

In a second terminal:

```bash
make ngrok
```

This prints a public URL like `https://abc123.ngrok.app`. Paste it
into:

- Slack app dashboard → Event Subscriptions → Request URL (append
  `/api/v1/webhooks/slack`)

Also export it so subprocesses pick it up:

```bash
export WEBHOOK_PUBLIC_URL=https://abc123.ngrok.app
```

## How it fits together

The build is complete; see `docs/ARCHITECTURE.md` and
`docs/SYSTEM_DESIGN.md` for the system design, and `docs/SETUP_SLACK.md`
/ `docs/SETUP_AUTH0.md` for connecting the external services.

## Useful commands

| | |
|---|---|
| `make up` | start stack |
| `make down` | stop stack (volumes preserved) |
| `make down-v` | stop + wipe volumes |
| `make logs` | tail all logs |
| `make logs-api` | tail api only |
| `make migrate` | run alembic migrations |
| `make migration name="add x"` | create autogen migration |
| `make psql` | open psql against the dev DB |
| `make shell-api` | python shell in api container |
| `make lint` | full lint |
| `make fmt` | auto-format |
| `make test` | unit tests |
| `make test-integration` | integration tests |
| `make e2e` | Playwright E2E |
| `make eval` | eval harness (Anthropic key required) |
| `make ngrok` | expose port 8000 publicly |

## Troubleshooting

**Containers refuse to start.** `docker compose down -v` then `make up`.

**Postgres healthcheck times out.** First-time pull is ~250MB; give it
a minute. If still failing, `docker compose logs postgres`.

**Pre-commit hook is slow.** First commit installs hook envs. Cached
after that.

**Anthropic 401.** Set `ANTHROPIC_API_KEY` in `.env` and `make up`
again to pick up env.

**Auth0 callback fails.** Check `AUTH0_DOMAIN` + `AUTH0_AUDIENCE` are
set and that the Auth0 app's "Allowed Callback URLs" includes
`http://localhost:3000/api/auth/callback`.
