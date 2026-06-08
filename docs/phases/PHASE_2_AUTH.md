# Phase 2 — Auth + tenancy

## Goal

Sign-in works end-to-end via Auth0. Every authenticated request to
the API arrives with a verified user + org identity, and the
Postgres session has `app.current_org_id` set so row-level security
(RLS) automatically scopes every query. Orgs and memberships are
populated via Auth0 webhooks on org / membership creation. By the
end of this phase a malicious user with a raw SQL console cannot
see another org's rows, full stop.

## Why this phase, this order

Auth is the foundation every other phase assumes. The Router agent
(phase 5) writes `message_tags` rows. The Cards builder (phase 6)
writes `cards` rows. The Digest agent (phase 8) reads `messages`
and writes `digests`. Every one of those reads and writes must be
tenant-scoped from day one — bolting tenancy on later means
auditing every query in the codebase, which is exactly the kind
of work that misses one and ships a data leak.

We do it now, before any tenant-scoped table holds real data,
because the cost of getting RLS wrong on an empty table is zero
and the cost of getting it wrong on a populated one is a
post-mortem.

The order inside the phase: Auth0 config + JWKS verification
first (you can't write middleware without something to verify),
middleware second (sets `app.current_org_id`), RLS policies third
(now the setting actually does something), webhooks last (data
flows in).

## Pre-requisites

- Phase 1 done (`make up`, test harness, env vars wired)
- Auth0 tenant created, regular web application set up, API
  registered with audience `https://api.evercurrent.local`
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_CLIENT_ID`,
  `AUTH0_CLIENT_SECRET`, `AUTH0_WEBHOOK_SECRET` populated in
  `.env`

## Files touched

### New
- `apps/api/src/evercurrent/auth/__init__.py`
- `apps/api/src/evercurrent/auth/auth0.py` — JWKS fetch + cache, token verify
- `apps/api/src/evercurrent/auth/deps.py` — `get_current_principal`, `get_current_org`
- `apps/api/src/evercurrent/auth/schemas.py` — `Auth0Claims`, `Principal` Pydantic models
- `apps/api/src/evercurrent/tenancy/__init__.py`
- `apps/api/src/evercurrent/tenancy/rls.py` — `set_org_context(session, org_id)`
- `apps/api/src/evercurrent/tenancy/middleware.py` — ASGI middleware
- `apps/api/src/evercurrent/api/routers/webhooks.py` — `POST /api/v1/webhooks/auth0`
- `apps/api/src/evercurrent/api/routers/me.py` — `GET /api/v1/me`
- `apps/api/alembic/versions/<rev>_orgs_memberships_rls.py`
- `apps/api/tests/integration/test_rls.py` — RLS bypass attempts
- `apps/api/tests/integration/test_auth_middleware.py`
- `apps/api/tests/integration/test_webhook_auth0.py`
- `apps/web/middleware.ts` — `@auth0/nextjs-auth0` route protection
- `apps/web/app/auth/[auth0]/route.ts` — Auth0 SDK dynamic route handlers
- `apps/web/app/login/page.tsx` — login button
- `apps/web/lib/auth0.ts` — Auth0 client config

### Modified
- `apps/api/src/evercurrent/main.py` — register middleware + webhooks router
- `apps/api/src/evercurrent/db/session.py` — accept org_id, call `set_org_context`
- `apps/api/pyproject.toml` — add `pyjwt[crypto]`, `httpx`, `cachetools`
- `apps/web/package.json` — add `@auth0/nextjs-auth0`
- `.env.example` — Auth0 keys documented

### Deleted
- nothing

## Tasks

1. **Auth0 setup (out of code).** In the Auth0 dashboard: enable
   Organizations, create a test org, register the Next.js app as a
   Regular Web Application, register the FastAPI as an API with
   audience `https://api.evercurrent.local`. Add the
   `org_id` claim to ID + access tokens via an Auth0 Action.
2. **Pydantic claims model.** `auth/schemas.py`:
   ```python
   class Auth0Claims(BaseModel):
       model_config = ConfigDict(strict=True, extra="ignore")
       sub: str                            # auth0_user_id
       org_id: str | None = None           # auth0_org_id
       aud: str | list[str]
       iss: str
       exp: int
   class Principal(BaseModel):
       auth0_user_id: str
       auth0_org_id: str
       org_id: UUID                        # our internal UUID
       membership_id: UUID
       role: str
   ```
3. **JWKS verifier.** `auth/auth0.py`:
   - Fetch `https://{AUTH0_DOMAIN}/.well-known/jwks.json` with httpx.
   - Cache the key set in-process with `cachetools.TTLCache(maxsize=1, ttl=3600)`.
   - `verify_token(token: str) -> Auth0Claims` uses `pyjwt.decode`
     with `audience=AUTH0_AUDIENCE`, `issuer=f"https://{AUTH0_DOMAIN}/"`,
     algorithm `RS256`. Raises `InvalidTokenError` on any failure.
4. **Migration.** `alembic revision -m "orgs_memberships_rls"`.
   Create `orgs` + `org_memberships` per SYSTEM_DESIGN.md §2.3
   (rename `clerk_org_id` → `auth0_org_id`, `clerk_user_id` →
   `auth0_user_id`). Then for every tenant-scoped table that
   exists at this point (just `orgs` + `org_memberships`):
   ```sql
   ALTER TABLE org_memberships ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation ON org_memberships
     USING (org_id = current_setting('app.current_org_id', TRUE)::uuid);
   ```
   `orgs` gets a special policy: `USING (id = current_setting(...)::uuid)`.
   We use `current_setting('...', TRUE)` (the second arg) so a missing
   setting returns NULL instead of raising — query then matches zero
   rows, which is fail-safe.
5. **Tenancy helper.** `tenancy/rls.py`:
   ```python
   async def set_org_context(session: AsyncSession, org_id: UUID) -> None:
       await session.execute(
           text("SELECT set_config('app.current_org_id', :v, TRUE)"),
           {"v": str(org_id)},
       )
   ```
   The `TRUE` makes it transaction-local — auto-cleared at commit/rollback,
   so a pooled connection can't leak the previous request's org.
6. **Middleware.** `tenancy/middleware.py`:
   - Extract Bearer token from `Authorization` header. Fall back to
     `appSession` cookie (set by `@auth0/nextjs-auth0` and forwarded
     by the Next.js BFF on same-origin proxied calls).
   - Call `verify_token`. On failure return 401.
   - Look up `org_memberships` row by `(auth0_org_id, auth0_user_id)`.
     If missing return 403 (user is authenticated but not provisioned).
   - Stash `Principal` on `request.state.principal`.
   - The DB session dependency reads `request.state.principal.org_id`
     and calls `set_org_context` before yielding the session.
7. **FastAPI deps.** `auth/deps.py`:
   ```python
   async def get_current_principal(request: Request) -> Principal: ...
   async def get_current_org(p: Principal = Depends(get_current_principal)) -> UUID:
       return p.org_id
   ```
8. **`/me` endpoint.** Returns `{ user_id, org_id, org_name, role }`.
   Frontend hits this on app load to bootstrap.
9. **Auth0 webhook.** `POST /api/v1/webhooks/auth0`:
   - Verify HMAC signature against `AUTH0_WEBHOOK_SECRET` (header
     `X-Auth0-Signature`).
   - Switch on `event.type`:
     - `organization.created` → insert into `orgs` (idempotent on
       `auth0_org_id`).
     - `organization.member.added` → upsert into `org_memberships`.
   - Webhook is exempt from the auth middleware (it has its own
     signature check).
10. **Next.js side.**
    - Install `@auth0/nextjs-auth0` v4.
    - `app/auth/[auth0]/route.ts` mounts the SDK route handlers.
    - `middleware.ts` calls `auth0.middleware(request)` — protects
      every route except `/login` and `/api/auth/*`.
    - `lib/auth0.ts` exports a singleton `Auth0Client`.
    - `app/login/page.tsx` is a server component with one
      `<a href="/auth/login">Sign in</a>` button.
    - Fetch wrapper in `apps/web/lib/api.ts` attaches the access
      token: `headers["Authorization"] = "Bearer " + token` where
      `token = await auth0.getAccessToken()`.
11. **Wire up.** Register `webhooks` + `me` routers in `main.py`.
    Add the auth middleware. Confirm `GET /api/v1/me` returns 401
    without a token and the user's org with one.
12. **Commit.** `feat(phase-2): auth0 + multi-tenancy with postgres RLS`.

## Test plan

TDD-first. Write each test, watch it fail, then implement.

1. **`test_rls.py::test_user_cannot_see_other_org_rows`** —
   Insert two orgs A and B with one membership each. Open a
   session, `set_org_context(A.id)`, raw SQL
   `SELECT * FROM org_memberships`. Assert only A's row returns.
   Switch to `set_org_context(B.id)`. Assert only B's row.
2. **`test_rls.py::test_rls_blocks_even_with_raw_sql`** —
   Same setup. With org A's context, attempt
   `SELECT * FROM org_memberships WHERE org_id = :b_id` with B's
   ID interpolated. Assert zero rows — the policy filters first.
3. **`test_rls.py::test_missing_org_context_returns_zero_rows`** —
   Fresh session, no `set_org_context`. Query any tenant-scoped
   table. Assert zero rows (because `current_setting(..., TRUE)`
   returns NULL and `NULL::uuid` does not match anything).
4. **`test_auth_middleware.py::test_rejects_no_token`** — `GET /me`
   without Authorization header → 401.
5. **`test_auth_middleware.py::test_rejects_unsigned_token`** —
   Hand-craft a JWT with `alg=none`. Request fails 401.
6. **`test_auth_middleware.py::test_rejects_wrong_audience`** —
   JWT signed with the right key but `aud=https://other.example` →
   401. Proves we don't accept tokens minted for a different API.
7. **`test_auth_middleware.py::test_rejects_expired_token`** —
   JWT with `exp` in the past → 401.
8. **`test_auth_middleware.py::test_accepts_valid_token_and_sets_org`** —
   Insert an org + membership. Mint a JWT signed by the test JWKS
   (use a local RSA keypair in the fixture, patch JWKS fetch).
   `GET /me` returns 200 with the right org.
9. **`test_webhook_auth0.py::test_org_created_is_idempotent`** —
   POST the same `organization.created` payload twice. Assert one
   row in `orgs`, second call returns 200.
10. **`test_webhook_auth0.py::test_membership_added_is_idempotent`** —
    Same, for `organization.member.added`. Unique constraint on
    `(org_id, auth0_user_id)` enforces it.
11. **`test_webhook_auth0.py::test_bad_signature_rejected`** —
    POST with wrong HMAC → 401.

## Definition of done

- [ ] `GET /api/v1/me` returns 401 without a token
- [ ] `GET /api/v1/me` with a valid token returns the user's org
- [ ] Migration creates `orgs` + `org_memberships` with RLS enabled
- [ ] `POST /api/v1/webhooks/auth0` creates org + membership rows
- [ ] Webhook idempotent on retry (verified by test)
- [ ] RLS test proves user A cannot read user B's rows, even with
      hand-crafted SQL
- [ ] Next.js `/login` page shows "Sign in" button; auth redirect
      round-trips successfully end-to-end
- [ ] Protected pages redirect to `/login` when no session
- [ ] `make lint` clean
- [ ] One commit on `feat/phase-2-auth` branch, merged to `main`

## Common pitfalls

- **JWKS cached forever.** If Auth0 rotates signing keys, your
  process is stuck verifying with the old key set until restart.
  `TTLCache(ttl=3600)` is enough — Auth0 rotation is rare and
  one-hour stale is acceptable.
- **`current_setting('app.current_org_id')` without the second arg.**
  Raises if unset. Always use `current_setting('app.current_org_id', TRUE)`.
- **Forgetting `is_local=TRUE` on `set_config`.** Without it the
  setting persists for the whole connection. The pool hands the
  connection to the next request and that request reads the
  previous tenant's org. Always pass `TRUE`.
- **Verifying issuer with trailing slash mismatch.** Auth0's `iss`
  claim is `https://{domain}/` *with* the trailing slash. Make
  sure your `pyjwt.decode(..., issuer=...)` matches exactly.
- **Webhook signature: raw body vs parsed.** HMAC must run over
  the raw request body bytes, before FastAPI parses them. Read
  `await request.body()` once, verify, then `json.loads` yourself
  — don't rely on a `pydantic.BaseModel` body parameter (it
  consumes the stream).
- **Auth0 Organizations not enabled in tenant.** The `org_id`
  claim won't appear in tokens unless you enable Organizations
  and use the org-scoped login URL.
- **Next.js middleware running on `_next/*` requests.** Default
  matcher catches static assets and stalls dev. Add a `matcher`
  exclusion: `'/((?!_next/static|_next/image|favicon.ico).*)'`.
- **Webhook race with `/me`.** User signs up, hits `/me` before
  the webhook arrives, sees 403. Mitigation: `/me` falls back to
  a JIT provision if the JWT has `org_id` but no membership row
  exists yet — create it inline, then return 200. Phase 2 ships
  the JIT path.

## Recap — what you'll be able to explain after this phase

- "How does the API know who's calling?" → Every request carries
  an Auth0-issued JWT. Middleware extracts it, verifies the
  RS256 signature against Auth0's JWKS (cached in-process for an
  hour), validates `aud` and `iss`, and resolves the user's
  internal `org_id` + `membership_id` via a single lookup on
  `org_memberships`.
- "Why JWT verification at middleware, not per route?" → Every
  protected route needs the same check. Centralising it means
  one place to audit, one place to log, zero chance of a route
  shipping unauthenticated by accident. Routes just declare
  `Depends(get_current_principal)` and read off `request.state`.
- "How is tenant isolation enforced?" → Postgres RLS. Every
  tenant-scoped table has a policy `USING (org_id =
  current_setting('app.current_org_id')::uuid)`. The middleware
  calls `set_config(..., is_local=TRUE)` once per request. If
  someone forgets to set the org or sets the wrong one, queries
  return zero rows — fail safe.
- "Why RLS at the DB layer instead of app-layer `WHERE org_id`?"
  → Defence in depth. App code can have bugs. A `WHERE` clause
  can be forgotten. RLS is the floor: even a raw SQL query from
  a misbehaving service can't escape its org. App-layer filters
  are a redundant belt; RLS is the suspenders.
- "Why store `auth0_org_id` as TEXT not parse it?" → It's an
  opaque identifier from a third party. Parsing it implies we
  understand its structure, which we don't and shouldn't. TEXT
  with a UNIQUE constraint matches the semantics: opaque,
  unique, never mutated by us.
- "How are orgs created in your DB?" → Auth0 fires
  `organization.created` to our webhook. We verify HMAC, insert
  on `auth0_org_id`. Idempotent: same payload twice is a no-op.

## Talking points (for the grill)

1. **"RLS is the floor, not the ceiling."** App-layer scoping is
   still nice for query performance and clarity, but RLS is the
   thing that survives a coding mistake. Show the policy.
2. **"Fail safe on missing context."** `current_setting(..., TRUE)`
   returns NULL, comparison returns NULL, row excluded. Forgetting
   to set the org returns zero rows, not all rows.
3. **"Transaction-local config."** `set_config(..., is_local=TRUE)`
   auto-clears at commit/rollback. Connection pooling cannot leak
   the previous tenant's org_id to the next request.
4. **"JWKS cached, not re-fetched per request."** `TTLCache` with
   one-hour TTL. Token verify is cheap.
5. **"Webhooks are the source of truth for membership."** We don't
   poll Auth0 — they push state changes, we mirror them. Webhook
   handlers are idempotent so retries cost nothing.
6. **"JIT provisioning closes the race."** Webhook can lose the
   race against a fast user. `/me` checks the JWT's `org_id`
   claim and provisions inline if the membership doesn't exist
   yet. Webhook arriving later is then a no-op.
7. **"Audience is non-negotiable."** A token minted for a
   different API is rejected even if signed by the same Auth0
   tenant. This is what stops the "stolen token from another
   service" attack.
