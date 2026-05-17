# apps/web — EverCurrent dashboard

Next.js 16.2 App Router · React 19 · Tailwind v4 · TanStack Query 5 ·
Zustand · Zod. SSE-driven, read-only viewport on the backend.

## Run

Everything is docker-only from the repo root.

```bash
# from repo root
make up                # builds + starts the full stack incl. web on nginx :8080
make lint              # eslint + prettier check + tsc, all inside docker
```

Open `http://localhost:8080`. The dashboard impersonates a user via
the dropdown; every per-user query (digest, decisions filter, feedback)
sends `X-Impersonate-User: <uuid>` so the backend personalises
without auth scaffolding.

## Pages

- `/dashboard` — Today banner + day switcher + phase switcher +
  Briefing (markdown + thumbs feedback).
- `/decisions` — extracted decisions filtered to the impersonated
  user's owned subsystems (toggle to show all).
- `/docs` — project documents tagged with the phases they're
  authoritative for. Highlights the active phase.

## Realtime

`hooks/use-events.ts` opens one `EventSource` on
`/api/events?project_id=...` per dashboard mount. The server pushes
`digest.updated`, `message.synthesized`, `phase.changed`,
`decisions.updated` over SSE; the hook invalidates the matching
TanStack Query keys. No periodic polling.

## Layout

```
apps/web/
├── app/
│   ├── layout.tsx               root + Providers (QueryClient)
│   ├── page.tsx                 redirect to /dashboard
│   ├── dashboard/page.tsx
│   ├── decisions/page.tsx
│   └── docs/page.tsx
├── components/
│   ├── ui/                      button, card, select, spinner
│   ├── layout/                  app-shell + impersonation dropdown
│   ├── digest/digest-card.tsx
│   └── simulation/              today-banner, day-switcher, phase-switcher
├── hooks/
│   └── use-events.ts            SSE subscription
├── lib/
│   ├── api.ts                   fetch wrapper + per-request impersonation header
│   ├── types.ts                 Zod schemas for every API response
│   └── utils.ts                 cn() helper
└── stores/impersonation.ts      Zustand store (project + user + day)
```
