---
paths:
  - "apps/web/**/*.ts"
  - "apps/web/**/*.tsx"
description: TypeScript and React coding standards for the EverCurrent frontend
---

# TypeScript rules (apps/web/)

Auto-loaded when editing any `.ts` or `.tsx` file under `apps/web/`. Codifies
the non-negotiables from `AGENTS.md` §7, plus React/Next.js specifics.

## Hard requirements

- **`strict: true`** in tsconfig. No turning it off.
- **No `any`.** Use `unknown` and narrow. If a library forces `any` at the
  boundary, narrow immediately.
- **Zod at every external boundary.** API responses, form input,
  localStorage reads, URL params if non-trivial.
- **Server components by default.** Add `"use client"` only when interactivity
  demands it (event handlers, browser APIs, state hooks).
- **TanStack Query for all server state.** No `useEffect` for data fetching.
- **Tailwind only.** No CSS modules, no styled-components, no emotion.
- **Lucide icons via shadcn.** No emojis in code.

## Naming

- Files: `kebab-case.tsx`. Components inside: `PascalCase`.
- Hooks: `use-camel-case.ts`, exported as `useCamelCase`.
- Types: `PascalCase`. Suffix with intent if helpful (`UserProps`,
  `MessageDto`, `DigestApiResponse`).
- Zod schemas: `userSchema` (lowercase). Inferred type: `User`.

## Component patterns

- Default export only for page components (`app/dashboard/page.tsx`). Named
  exports everywhere else.
- Co-locate component-specific types in the same file. Lift to `lib/types.ts`
  only when shared across files.
- Props are explicit interfaces, not destructured anonymous types:
  ```tsx
  interface DigestCardProps {
    digest: Digest;
    onFeedback: (messageId: string, signal: -1 | 1) => void;
  }

  export function DigestCard({ digest, onFeedback }: DigestCardProps) { ... }
  ```
- No `React.FC`. Use plain function components with explicit prop types.

## Server vs client components

- **Server component (default):** can fetch data directly, can render
  components, cannot use state/effects/event handlers.
- **Client component (`"use client"` at top):** can use hooks, event
  handlers, browser APIs. Lazy-load if it's heavy.
- **Decision rule:** if the component needs `useState`, `useEffect`,
  `useRef`, an event handler, or browser APIs, it's a client component.
  Otherwise it's a server component.
- Pass server-fetched data DOWN to client components as props. Don't refetch
  in the client when the server already has it.

## Data fetching with TanStack Query

- One `useQuery` per resource. Co-located with the component that owns it.
- Query keys are tuples: `['digest', userId, day]`.
- Invalidation after mutations: explicit `queryClient.invalidateQueries`.
- Optimistic updates for feedback buttons (immediate UI response).
- Use `useSuspenseQuery` if the parent has a Suspense boundary.

## State management

- **Local state first** (`useState`). Lift when needed.
- **Server state** in TanStack Query.
- **Client state across components** in Zustand stores at `apps/web/stores/`.
  Use sparingly. The impersonation store is the prototypical use case.
- No Redux, no MobX, no Recoil, no Jotai. Zustand is sufficient and chosen.

## Styling

- Tailwind utility classes. Use `cn()` helper (from `clsx` + `tailwind-merge`)
  for conditional class composition.
- Design tokens via Tailwind theme. No magic numbers.
- shadcn/ui components live in `apps/web/components/ui/`. Modified, not
  treated as a third-party library.

## Forms

- React Hook Form + Zod resolver for any form beyond a single input.
- Server actions can be used for form submission when appropriate.
- Validate on the server too. Never trust client-side validation alone.

## Streaming and SSE

- Agent chat uses Server-Sent Events.
- Parser lives in `apps/web/lib/stream.ts` and yields typed events.
- Components consume events via a custom hook (`useAgent`) that manages
  the EventSource-like connection.

## Anti-patterns Claude should not write

- `as` type assertions except where genuinely necessary. Prefer Zod parsing
  or proper type guards.
- `useEffect` for data fetching.
- `useEffect` to sync state across components (use Zustand or lift state).
- Inline anonymous components: `() => <div />` in JSX (causes re-renders).
- `console.log` left in committed code.
- Inline comments and JSDoc. The code is the description; rename instead.
  Keep only functional directives (`// eslint-disable`, `// @ts-expect-error`)
  and `"use client"` / `"use server"`.

## When you're about to add a dependency

Stop. Check `package.json`. If not listed, ask the user. The stack is
deliberate.

## File and component size

- Components over 200 lines: split into smaller components.
- Files over 300 lines: split or extract.
- Functions over 50 lines: usually a smell.

Smells, not laws. Use judgment.
