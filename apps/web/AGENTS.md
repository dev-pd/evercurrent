<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

<!-- END:nextjs-agent-rules -->

# Frontend conventions (`apps/web`)

Loaded for frontend work via `apps/web/CLAUDE.md`. Repo-wide standards
(architecture, git, testing) live in the root `AGENTS.md`. Installed
Next 16.2 / React 19 / Tailwind v4 APIs differ from training data — see the
warning above. Non-obvious project calls:

- **No `useEffect` for data fetching** — TanStack Query for all server state
  (one `useQuery` per resource, tuple keys, explicit invalidation).
- Zod validates **every** external boundary (API responses, forms,
  localStorage, non-trivial URL params).
- Server components by default; `"use client"` only when interactivity demands.
- Zustand for cross-component client state, sparingly. No Redux/MobX/Recoil/Jotai.
- No `any` (use `unknown` + narrow). No `as` assertions unless unavoidable.
- Naming: `kebab-case.tsx` files, `PascalCase` components, `use-camel-case.ts`
  hooks, lowercase Zod schemas. Named exports except page components.
- SSE: parser in `lib/stream.ts`, consumed via the `useAgent` hook. Keep the
  listener alive past UI timeouts so a late event still lands.
- Tailwind only (`cn()` helper for conditionals). Lucide via shadcn, no emojis.
- Smells: component >200 lines, file >300 lines.
