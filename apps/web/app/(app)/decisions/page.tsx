export const dynamic = "force-dynamic";

import Link from "next/link";
import { ArrowUpRight, GitBranch, MessageSquare } from "lucide-react";
import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
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

const KIND_STYLES: Record<string, string> = {
  decision: "border-emerald-200 bg-emerald-50 text-emerald-700",
  risk: "border-amber-200 bg-amber-50 text-amber-700",
  question: "border-sky-200 bg-sky-50 text-sky-700",
  action: "border-violet-200 bg-violet-50 text-violet-700",
};

function kindStyle(kind: string): string {
  return KIND_STYLES[kind] ?? "border-zinc-200 bg-zinc-50 text-zinc-700";
}

export default async function DecisionsPage({ searchParams }: DecisionsPageProps) {
  const params = await searchParams;
  const cards = await safeListCards(params.project_id);
  const filtered = cards.filter((c) => {
    if (params.kind && c.kind !== params.kind) return false;
    if (params.status && c.status !== params.status) return false;
    return true;
  });

  return (
    <PageContainer>
        <PageHeader
          title="Decisions"
          subtitle="Structured decisions, risks, and actions extracted from team chatter and docs."
          action={
            <span className="font-mono text-xs tabular-nums text-[var(--text-muted)]">
              {filtered.length}/{cards.length}
            </span>
          }
          toolbar={
            <div className="flex flex-wrap gap-1.5">
              <FilterChip href="/decisions" label="All" active={!params.kind && !params.status} />
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
              <FilterChip
                href="/decisions?kind=action"
                label="Actions"
                active={params.kind === "action"}
              />
            </div>
          }
        />

        {filtered.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">
              No cards match this filter.
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Try a different filter or run a digest regeneration.
            </p>
          </div>
        ) : (
          <ul className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
            {filtered.map((card, idx) => (
              <li
                key={card.id}
                className={`group flex items-start gap-4 p-4 hover:bg-[var(--surface-muted)] ${
                  idx > 0 ? "border-t border-[var(--border-default)]" : ""
                }`}
              >
                <span
                  className={`mt-0.5 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${kindStyle(card.kind)}`}
                >
                  {card.kind}
                </span>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/decisions/${card.id}`}
                    className="block text-sm font-medium text-[var(--text-primary)] hover:text-[var(--color-accent-700)]"
                  >
                    {card.summary}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-[var(--text-muted)]">
                    <span className="font-mono uppercase tracking-wider">
                      {card.status}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" aria-hidden="true" />
                      {card.sources_count}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <GitBranch className="h-3 w-3" aria-hidden="true" />
                      {card.edges_count}
                    </span>
                  </div>
                </div>
                <ArrowUpRight
                  className="h-4 w-4 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
                  aria-hidden="true"
                />
              </li>
            ))}
          </ul>
        )}
    </PageContainer>
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
          ? "rounded-md border border-[var(--color-accent-600)] bg-[var(--color-accent-600)] px-2.5 py-1 text-xs font-medium text-white"
          : "rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
      }
    >
      {label}
    </Link>
  );
}
