---
name: add-react-component
description: |
  Use this skill when adding a new React component to the EverCurrent frontend,
  including: feature components in apps/web/components/, page components in
  apps/web/app/, layout components, or wrappers around shadcn/ui primitives.
  Covers server vs client component decision, prop typing, file naming,
  TanStack Query for server state, and Tailwind styling conventions.
---

# Add a React component

Use when adding a new component anywhere under `apps/web/`.

## Decide: server or client component?

This is the first decision. Get it right.

**Server component (default) if the component:**
- Only renders content (no event handlers)
- Fetches data (it can `await` directly)
- Doesn't need `useState`, `useEffect`, `useRef`
- Doesn't use browser APIs (window, localStorage, etc.)

**Client component (`"use client"` at top) if the component:**
- Uses any React hook
- Has `onClick`, `onChange`, or other event handlers
- Needs access to browser APIs
- Uses TanStack Query (it requires a client context)
- Uses Zustand store

If parent is a server component and child needs to be a client component,
that's fine. Pass server-fetched data as props.

## File placement

```
apps/web/
├── app/                       Pages and layouts (routing)
│   ├── dashboard/page.tsx     A page
│   └── dashboard/layout.tsx   A layout
├── components/
│   ├── ui/                    shadcn primitives (button, card, dialog)
│   ├── digest/                Feature-scoped components
│   │   ├── digest-card.tsx
│   │   └── feedback-buttons.tsx
│   ├── chat/
│   ├── simulation/
│   └── layout/                Shared layout (sidebar, header)
├── hooks/                     Custom hooks (use-*.ts)
├── lib/                       Utilities, API client, types
└── stores/                    Zustand stores
```

- Feature components live in `components/<feature>/`.
- File names are `kebab-case.tsx`.
- Component names inside are `PascalCase`.

## Prop typing

Explicit interface, no anonymous types:

```tsx
interface DigestCardProps {
  digest: Digest;
  onFeedback: (messageId: string, signal: -1 | 1) => void;
}

export function DigestCard({ digest, onFeedback }: DigestCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{digest.userName}'s briefing</CardTitle>
      </CardHeader>
      <CardContent>
        {/* ... */}
      </CardContent>
    </Card>
  );
}
```

No `React.FC`. No anonymous destructured types.

## Server component template

```tsx
// app/dashboard/page.tsx
import { fetchDigest } from "@/lib/api";
import { DigestCard } from "@/components/digest/digest-card";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ day?: string }>;
}) {
  const { day } = await searchParams;
  const currentDay = Number(day ?? 1);
  const digest = await fetchDigest({ day: currentDay });

  return <DigestCard digest={digest} />;
}
```

## Client component template

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useImpersonationStore } from "@/stores/impersonation";
import { fetchDigest } from "@/lib/api";

interface DigestViewProps {
  day: number;
}

export function DigestView({ day }: DigestViewProps) {
  const userId = useImpersonationStore((s) => s.currentUserId);

  const { data, isLoading, error } = useQuery({
    queryKey: ["digest", userId, day],
    queryFn: () => fetchDigest({ userId, day }),
  });

  if (isLoading) return <DigestSkeleton />;
  if (error) return <DigestError error={error} />;
  if (!data) return null;

  return <DigestCard digest={data} />;
}
```

## Styling

- Tailwind utility classes.
- Use `cn()` helper from `@/lib/utils` for conditional class composition:

```tsx
import { cn } from "@/lib/utils";

<button
  className={cn(
    "rounded-md px-3 py-1.5 text-sm font-medium",
    isActive && "bg-primary text-primary-foreground",
    disabled && "opacity-50 cursor-not-allowed",
  )}
/>
```

- No inline `style={{}}` except where dynamic computed values require it.
- No CSS-in-JS, no CSS modules.

## Icons

```tsx
import { ThumbsUp, ThumbsDown, MessageSquare } from "lucide-react";

<button>
  <ThumbsUp className="size-4" />
</button>
```

Outline icons. No emojis.

## When to use shadcn vs custom

- Use shadcn primitives (Button, Card, Dialog, Select, etc.) wherever
  applicable. Add via `pnpm dlx shadcn@latest add <component>`.
- Wrap shadcn primitives in feature components when there's repeated usage
  with a specific shape (e.g. `<DigestCard>` wraps `<Card>` with a known
  layout).

## Data fetching reminders

- Server components: `await fetch(...)` or call API client directly.
- Client components: TanStack Query.
- Mutations: `useMutation`, with `onSuccess` invalidating affected queries.
- Optimistic updates: use `queryClient.setQueryData` in `onMutate`, revert
  in `onError`.

## Loading and error states

Every async component has three states. Render all three:

```tsx
if (isLoading) return <DigestSkeleton />;
if (error) return <ErrorState error={error} />;
if (!data) return <EmptyState />;
return <DigestCard digest={data} />;
```

Skeletons live in the same file or alongside the component.

## Checklist before considering a component done

- [ ] Correct server/client decision
- [ ] Explicit props interface
- [ ] Loading, error, empty states (if async)
- [ ] Tailwind for all styling, `cn()` for conditional classes
- [ ] Lucide icons, no emojis
- [ ] Named export (default only for pages)
- [ ] File name kebab-case, component name PascalCase
- [ ] No `console.log` left in
- [ ] No `useEffect` for data fetching

## Common mistakes

- Marking a component `"use client"` when it doesn't need it (loses RSC
  benefits).
- Forgetting `"use client"` when using a hook (crashes).
- Inline anonymous components in JSX (causes re-renders).
- Using `useState` for server state instead of TanStack Query.
- Returning early without a skeleton (layout jumps).
