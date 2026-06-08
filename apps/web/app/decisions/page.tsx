import Link from "next/link";
import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import type { CardListItem } from "@/lib/types";

async function safeListCards(projectId: string | undefined): Promise<CardListItem[]> {
  try {
    const client = await apiServer();
    return await client.listCards(projectId ? { projectId } : undefined);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("decisions list fetch failed", error);
    }
    return [];
  }
}

interface DecisionsPageProps {
  searchParams: Promise<{ project_id?: string; kind?: string; status?: string }>;
}

export default async function DecisionsPage({ searchParams }: DecisionsPageProps) {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/decisions");
  }

  const params = await searchParams;
  const cards = await safeListCards(params.project_id);

  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <header className="flex items-end justify-between border-b border-zinc-200 pb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Decisions</h1>
          <span className="text-xs text-zinc-500">{cards.length} cards</span>
        </header>

        <div className="flex flex-wrap gap-2">
          <FilterChip
            href="/decisions"
            label="All"
            active={!params.kind && !params.status}
          />
          <FilterChip
            href="/decisions?status=open"
            label="Open"
            active={params.status === "open"}
          />
          <FilterChip
            href="/decisions?kind=decision"
            label="Decisions"
            active={params.kind === "decision"}
          />
          <FilterChip
            href="/decisions?kind=risk"
            label="Risks"
            active={params.kind === "risk"}
          />
        </div>

        {cards.length === 0 ? (
          <p className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-500">
            No cards yet.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {cards.map((card) => (
              <li
                key={card.id}
                className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">
                    {card.kind}
                  </span>
                  <span>status: {card.status}</span>
                  <span>{card.sources_count} sources</span>
                  <span>{card.edges_count} edges</span>
                </div>
                <Link
                  href={`/decisions/${card.id}`}
                  className="mt-2 block text-sm font-medium text-zinc-900 hover:text-zinc-700"
                >
                  {card.summary}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}

interface FilterChipProps {
  href: string;
  label: string;
  active: boolean;
}

function FilterChip({ href, label, active }: FilterChipProps) {
  return (
    <Link
      href={href}
      className={
        active
          ? "rounded-full border border-zinc-900 bg-zinc-900 px-3 py-1 text-xs font-medium text-white"
          : "rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
      }
    >
      {label}
    </Link>
  );
}
