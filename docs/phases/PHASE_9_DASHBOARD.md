# Phase 9 — Dashboard FE

## Goal

The surface the user sees. Next.js 16 App Router with Auth0 login,
the cards-first dashboard from PRD §7.2, live updates over SSE, and
the Knowledge Card detail view. When a reviewer signs in to the demo
they land on `/dashboard`, see their morning briefing, can thumbs
items, can click into any Card, can regenerate. New messages flowing
in from Slack appear in the "live updates" badge without a refresh.

This is the demo's hero screen. Everything previous phases built —
auth, ingest, router, cards, scoring, digest — surfaces here.

## Why this phase, this order

By phase 8 the backend is complete enough to render a useful UI. The
digest endpoint returns markdown + items, the cards endpoint returns
detail, SSE streams events. Building the FE earlier would block on
half-finished schemas; building it later sacrifices polish time
before the take-home demo.

The FE is built last on purpose. Once the API is stable the frontend
is mostly fetch + render. The cards-first design from PRD §7.2 maps
1:1 onto the data model: digest sections wrap `DigestItem`s, the
"you might be missing" surface wraps anomaly nudges, the cards page
wraps the `cards` table.

Server components by default. Auth0's Next.js SDK handles the OAuth
dance and session cookie. TanStack Query handles server state.
`useEffect` for data fetching is forbidden — TanStack owns that.

The order inside the phase: Auth0 wiring first (nothing renders until
sign-in works), shell + layout second, dashboard page third (server-
side fetch), client components fourth (the parts that need
interactivity), hooks + SSE fifth (live updates), card detail last.

## Pre-requisites

- Phase 2 (Auth0 wired on the backend, JWKS verifier, `/api/v1/me`
  returns principal)
- Phase 6 (cards endpoints serve `GET /api/v1/cards`,
  `GET /api/v1/cards/{id}`)
- Phase 7 (scores exist so digest items have something to rank)
- Phase 8 (digest endpoints serve `GET /api/v1/digests/today`,
  `POST /api/v1/digests/regenerate`, SSE publishes `digest_ready`)
- `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`,
  `AUTH0_SECRET`, `AUTH0_BASE_URL`, `AUTH0_AUDIENCE` in
  `apps/web/.env.local`
- Backend reachable at `NEXT_PUBLIC_API_URL`

## Files touched

### New
- `apps/web/app/api/auth/[...auth0]/route.ts` — Auth0 catch-all
- `apps/web/app/layout.tsx` — `UserProvider`, fonts, theme
- `apps/web/app/page.tsx` — redirect to `/dashboard` or `/api/auth/login`
- `apps/web/app/dashboard/page.tsx` — server component, hero screen
- `apps/web/app/decisions/page.tsx` — cards list
- `apps/web/app/decisions/[id]/page.tsx` — card detail
- `apps/web/components/dashboard/digest-header.tsx`
- `apps/web/components/dashboard/digest-section.tsx`
- `apps/web/components/dashboard/digest-item-card.tsx`
- `apps/web/components/dashboard/anomaly-banner.tsx`
- `apps/web/components/dashboard/live-updates-badge.tsx`
- `apps/web/components/cards/knowledge-card.tsx`
- `apps/web/components/cards/card-source-list.tsx`
- `apps/web/components/cards/card-edges-list.tsx`
- `apps/web/hooks/use-today.ts`
- `apps/web/hooks/use-digest.ts`
- `apps/web/hooks/use-cards.ts`
- `apps/web/hooks/use-events.ts`
- `apps/web/hooks/use-feedback.ts`
- `apps/web/lib/api.ts` — fetch wrapper with Auth0 access token
- `apps/web/__tests__/dashboard/digest-item-card.test.tsx`
- `apps/web/__tests__/dashboard/anomaly-banner.test.tsx`
- `apps/web/__tests__/hooks/use-feedback.test.tsx`
- `apps/web/__tests__/mocks/handlers.ts` — MSW request handlers
- `apps/web/e2e/sign-in-to-dashboard.spec.ts` — Playwright

### Modified
- `apps/web/lib/types.ts` — add Zod schemas: `CardSchema`,
  `CardSourceSchema`, `EdgeSchema`, `DigestSchema`, `DigestItemSchema`
- `apps/web/middleware.ts` — Auth0 `withMiddlewareAuthRequired`
- `apps/web/package.json` — add `@auth0/nextjs-auth0`
- `apps/web/.env.example`

### Deleted
- any prior `app/login` stub from phase 2 if it conflicts with the
  Auth0 catch-all

## Tasks

1. **Auth0 SDK install + config.** Add `@auth0/nextjs-auth0`.
   `app/api/auth/[...auth0]/route.ts` exports
   `handleAuth({ login: handleLogin({ authorizationParams: {
   audience: process.env.AUTH0_AUDIENCE } }) })`. Wrap `app/layout.tsx`
   in `<UserProvider>`.
2. **Middleware gate.** `apps/web/middleware.ts`:
   `export default withMiddlewareAuthRequired();` with matcher for
   `/dashboard/:path*`, `/decisions/:path*`. Public routes:
   `/`, `/api/auth/*`.
3. **Root entry.** `app/page.tsx` server component reads
   `getSession()`. If session → `redirect('/dashboard')`; else
   `redirect('/api/auth/login')`.
4. **API client.** `lib/api.ts`:
   - `apiFetch<T>(path, schema: ZodSchema<T>, init?)`:
     - On the server, gets the access token via
       `getAccessToken({ authorizationParams: { audience } })`.
     - On the client, calls a thin `/api/proxy/[...path]` route that
       attaches the token from the session.
     - `fetch` against `NEXT_PUBLIC_API_URL`, parses JSON,
       validates with `schema.parse`, returns `T`. Throws typed
       `ApiError` on non-2xx.
5. **Zod schemas.** Extend `lib/types.ts` with `CardSchema`,
   `DigestSchema`, `DigestItemSchema`, `EdgeSchema`,
   `ProjectTodaySchema`. Every API boundary parses through these.
6. **Dashboard page (server component).** `app/dashboard/page.tsx`:
   - In parallel: `apiFetch('/api/v1/projects/{id}/today',
     ProjectTodaySchema)` and `apiFetch('/api/v1/digests/today',
     DigestSchema)`.
   - Pass results as props to a client `<DashboardClient>` wrapper
     that handles SSE + feedback. Server-rendered HTML is the
     first paint.
7. **Components.** Build top-down:
   - `DigestHeader`: project name, current phase, day index,
     regenerate button (client component for the button).
   - `DigestSection`: groups items by `bucket`. Three sections in
     fixed order: top_priority, watch_outs, fyi.
   - `DigestItemCard`: source line, why-this-matters, thumbs
     up/down, "Open card" link if `card_id` present. Client
     component (uses `useFeedback`).
   - `KnowledgeCard`: summary, body, sources, edges, activity.
     Pure server component on the detail page.
   - `CardSourceList`, `CardEdgesList`: pure presentation.
   - `AnomalyBanner`: bottom-of-dashboard "you might be missing"
     surface; hidden when empty.
   - `LiveUpdatesBadge`: client component; subscribes via
     `useEvents`, counts new items since `digest.generated_at`.
8. **Hooks.** `apps/web/hooks/`:
   - `use-today.ts`: TanStack Query for project today data.
     `queryKey: ['today', projectId]`.
   - `use-digest.ts`: TanStack Query for `/digests/today`.
     Subscribes to `digest_ready` SSE event → invalidates query →
     refetches.
   - `use-cards.ts`: TanStack Query list + by-id.
   - `use-events.ts`: returns an `EventSource` bound to
     `/api/v1/events/stream?project_id=...`, dispatches events to a
     callback. Single connection per dashboard mount.
   - `use-feedback.ts`: `useMutation` for thumbs up/down → posts to
     `POST /api/v1/cards/{id}/feedback` and the topic-weights
     endpoint. Optimistic update: flip the UI state immediately,
     roll back on error.
9. **Decisions page.** `app/decisions/page.tsx` lists cards with
   filter chips. `app/decisions/[id]/page.tsx` server-fetches the
   card and renders `<KnowledgeCard>`.
10. **Tests.** Vitest + RTL for components + hooks, MSW for fetch
    mocking, one Playwright E2E.
11. **`make lint`, `make test`, `pnpm e2e`.** All green.
12. **Commit.** `feat(phase-9): dashboard FE — auth0, cards-first, live updates`.

## Test plan

Frontend tests live under `apps/web/__tests__/` (Vitest) and
`apps/web/e2e/` (Playwright). MSW mocks the API at the fetch boundary
so component tests don't depend on a running backend.

Component tests (Vitest + RTL):

- `digest-item-card.test.tsx`:
  - Renders source, author, why-this-matters in default state.
  - Shows "Open card" link only when `card_id` is present.
  - Thumbs up fires `useFeedback` mutation with `{useful: true}`.
  - Thumbs down fires with `{useful: false}`.
  - Disables both buttons while mutation is pending.
- `digest-section.test.tsx`:
  - Renders items in input order under the right bucket heading.
  - Renders nothing when items list is empty.
- `anomaly-banner.test.tsx`:
  - Hidden when `anomalies` prop is empty.
  - Shows count + source list when populated.
  - Clicking source link navigates to card.
- `digest-header.test.tsx`:
  - Renders project name + phase + day index.
  - Regenerate button fires the regenerate mutation; shows spinner
    while pending; shows toast on success.
- `live-updates-badge.test.tsx`:
  - Subscribes to a mocked EventSource; increments count on
    `message_tagged` events; resets to 0 on `digest_ready`.
- `knowledge-card.test.tsx`:
  - Renders summary, body, sources list, edges list.
  - "Pin" button toggles state.

Hook tests (Vitest):

- `use-feedback.test.tsx`:
  - Optimistic update flips UI before request resolves.
  - Rolls back on error.
- `use-events.test.tsx`:
  - Opens one EventSource on mount, closes on unmount.
  - Dispatches received events to the callback.

E2E (Playwright, single happy path):

- `sign-in-to-dashboard.spec.ts`:
  - Hit `/`. Get redirected to Auth0 (dev tenant) login.
  - Sign in with a seeded test user.
  - Land on `/dashboard`. Assert the digest header renders the
    seeded project name. Assert at least one `DigestItemCard` is
    visible.

Tests we deliberately do NOT write:

- Visual regression on the LLM-generated digest prose. Eval harness
  on the backend (phase 8) covers that.
- Cross-browser matrix. One Playwright in Chromium is enough for
  the take-home demo.

## Definition of done

- [ ] Sign-in via Auth0 dev tenant works end-to-end
- [ ] `/dashboard` renders digest header, three sections, items with
      feedback buttons
- [ ] Thumbs up/down POSTs feedback and updates UI optimistically
- [ ] Regenerate button enqueues a regen and shows the fresh digest
      when the SSE `digest_ready` event fires
- [ ] `/decisions` lists open cards; clicking opens the card detail
- [ ] `LiveUpdatesBadge` increments on `message_tagged` SSE events
- [ ] Every API response parses through a Zod schema; bad payload =
      typed error, not a crash
- [ ] All Vitest component + hook tests pass
- [ ] Playwright sign-in spec passes against a seeded backend
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm test` all clean
- [ ] One commit on `feat/phase-9-dashboard` branch, merged to `main`

## Common pitfalls

- **Auth0 callback URL mismatch.** Add
  `http://localhost:3000/api/auth/callback` to the Auth0 application's
  Allowed Callback URLs. The error message is unhelpful when this is
  wrong.
- **Audience missing on login.** Without
  `authorizationParams: { audience }`, the access token is an opaque
  Auth0 token, not the JWT the FastAPI backend expects. Add it in the
  `handleLogin` config.
- **Server components calling `fetch` without credentials.** Server
  components don't get the session cookie automatically. Use
  `getAccessToken` from `@auth0/nextjs-auth0`, attach as Bearer.
- **`useEffect` for data fetching.** Forbidden. TanStack Query owns
  it. Suspense + server prefetch on the page, hydrate, then refetch
  on client.
- **Multiple EventSource connections.** Mount `useEvents` once at the
  layout level for `/dashboard`. Don't open one per component, or
  the browser hits its per-origin limit.
- **SSE through Auth0 middleware breaks streaming.** The Next.js
  middleware doesn't proxy SSE well. Connect directly to the
  backend's `/api/v1/events/stream`, not through a Next.js API
  route.
- **Zod schemas drifting from backend.** Keep them in `lib/types.ts`
  next to the API client. When backend schema changes, FE typecheck
  catches the mismatch at build time. Don't `z.any()`.
- **Optimistic feedback that doesn't roll back.** `useFeedback`'s
  `onError` must restore the previous state, or a network glitch
  leaves the UI lying about whether the user thumbed.
- **Tailwind v4 config mismatch.** v4 uses `@theme` in CSS, not
  `tailwind.config.js`. Use the v4 patterns; don't copy v3 examples.
- **Playwright flakiness on Auth0 redirect.** Use Auth0's test
  credentials and `page.waitForURL('/dashboard')` instead of fixed
  timeouts. Set `AUTH0_DOMAIN` to a dev tenant only.

## Recap — what you'll be able to explain after this phase

- "Why server components by default?" → Less client JavaScript means
  faster TTFB and smaller bundles. Auth0 session lives server-side so
  the access token never reaches the client. Only the interactive
  bits — feedback buttons, SSE subscriber, regenerate button — are
  `"use client"`.
- "Why TanStack Query, not Redux?" → Server state is already a solved
  problem: caching, invalidation, optimistic updates, retries. Redux
  reinvents all of that. TanStack pairs naturally with SSE: an event
  invalidates a query key and the next render is fresh.
- "Why Zod at the API boundary?" → Runtime safety. The backend is
  Python; TypeScript types alone can't catch a missing field. Zod
  parses and narrows; bad data raises a typed error we can surface,
  not a silent `undefined` deep in render. Types are derived from
  the schemas, so the static and runtime worlds agree by
  construction.
- "Why Auth0 SDK over rolling JWT verification?" → Battle-tested
  session management, callback handling, refresh-token rotation, and
  CSRF protection. We could write it; we shouldn't.
- "How do live updates work end-to-end?" → Worker publishes to Redis
  channel `events:<org_id>` after each pipeline step. FastAPI
  `/events/stream` subscribes and forwards as SSE. The dashboard
  mounts one EventSource via `useEvents`. On `digest_ready`,
  `use-digest` invalidates its query key; TanStack refetches; the
  UI swaps in the new digest. No polling.
- "How do you stop the FE from re-fetching everything on every
  event?" → Targeted query keys. `message_tagged` increments a
  counter only; it does not invalidate the digest. The user clicks
  to refresh, or the next `digest_ready` fires.

## Talking points (for the grill)

1. **"Server-first React."** Auth on the server, fetch on the
   server, hydrate the client only where interactivity lives.
2. **"Zod is the contract."** Every API response is parsed. Static
   types are derived from schemas, not declared independently.
3. **"TanStack Query + SSE = correct server state."** Events
   invalidate, queries refetch, optimistic mutations roll back on
   failure.
4. **"Auth0 SDK, not handmade JWT."** Session + refresh +
   middleware in one library.
5. **"Cards-first UI."** The dashboard maps 1:1 onto the data model.
   Sections wrap buckets, items wrap scored messages, "you might
   be missing" wraps the anomaly nudge.
6. **"One EventSource per dashboard mount."** Avoids the per-origin
   connection cap.
7. **"Vitest + MSW for components, Playwright for the one happy
   path."** Component tests are fast and many; E2E is slow and one.
8. **"Optimistic feedback is a UX choice, not laziness."** Thumbs
   land instantly; rollback on error is the contract.
