"use client";

import { useState } from "react";
import { ArrowUpRight, GitBranch, MessageSquare } from "lucide-react";
import type { CardListItem } from "@/lib/types";
import { useDecisionModal } from "@/stores/decision-modal";

const KIND_STYLES: Record<string, string> = {
  decision: "border-emerald-200 bg-emerald-50 text-emerald-700",
  risk: "border-amber-200 bg-amber-50 text-amber-700",
  question: "border-sky-200 bg-sky-50 text-sky-700",
};

function kindStyle(kind: string): string {
  return KIND_STYLES[kind] ?? "border-zinc-200 bg-zinc-50 text-zinc-700";
}

type Filter =
  | { key: "mine" }
  | { key: "all" }
  | { key: "open" }
  | { key: "kind"; kind: "decision" | "risk" | "question" };

function buildFilters(hasSubs: boolean): { label: string; filter: Filter }[] {
  return [
    ...(hasSubs ? [{ label: "Mine (open)", filter: { key: "mine" } as Filter }] : []),
    { label: "All open", filter: { key: "open" } },
    { label: "Decisions", filter: { key: "kind", kind: "decision" } },
    { label: "Risks", filter: { key: "kind", kind: "risk" } },
    { label: "Questions", filter: { key: "kind", kind: "question" } },
    { label: "All", filter: { key: "all" } },
  ];
}

function inMyScope(card: CardListItem, mySubs: string[]): boolean {
  if (card.status !== "open") return false;
  if (mySubs.length === 0) return true;
  return card.affected_subsystems.some((s) => mySubs.includes(s));
}

function matches(card: CardListItem, f: Filter, mySubs: string[]): boolean {
  if (f.key === "all") return true;
  if (f.key === "open") return card.status === "open";
  if (f.key === "kind") return inMyScope(card, mySubs) && card.kind === f.kind;
  return inMyScope(card, mySubs);
}

function isActive(a: Filter, b: Filter): boolean {
  if (a.key !== b.key) return false;
  if (a.key === "kind" && b.key === "kind") return a.kind === b.kind;
  return true;
}

export function DecisionsBoard({
  cards,
  mySubsystems = [],
}: {
  cards: CardListItem[];
  mySubsystems?: string[];
}) {
  const hasSubs = mySubsystems.length > 0;
  const filters = buildFilters(hasSubs);
  const [filter, setFilter] = useState<Filter>(hasSubs ? { key: "mine" } : { key: "open" });
  const filtered = cards.filter((c) => matches(c, filter, mySubsystems));
  const open = useDecisionModal((s) => s.open);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        {filters.map(({ label, filter: f }) => {
          const active = isActive(f, filter);
          return (
            <button
              key={label}
              type="button"
              onClick={() => setFilter(f)}
              className={
                active
                  ? "rounded-md border border-[var(--color-accent-600)] bg-[var(--color-accent-600)] px-2.5 py-1 text-xs font-medium text-white"
                  : "rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
              }
            >
              {label}
            </button>
          );
        })}
        <span className="ml-auto font-mono text-xs text-[var(--text-muted)] tabular-nums">
          {filtered.length}/{cards.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
          <p className="text-sm font-medium text-[var(--text-primary)]">No cards match this filter.</p>
        </div>
      ) : (
        <ul className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
          {filtered.map((card, idx) => (
            <li
              key={card.id}
              className={idx > 0 ? "border-t border-[var(--border-default)]" : ""}
            >
              <button
                type="button"
                onClick={() => open(card.id)}
                className="group flex w-full items-start gap-4 p-4 text-left hover:bg-[var(--surface-muted)]"
              >
                <span
                  className={`mt-0.5 w-[72px] shrink-0 rounded-md border py-0.5 text-center text-[10px] font-semibold tracking-wider uppercase ${kindStyle(card.kind)}`}
                >
                  {card.kind}
                </span>
                <div className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--color-accent-700)]">
                    {card.summary}
                  </span>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-[var(--text-muted)]">
                    <span className="font-mono tracking-wider uppercase">{card.status}</span>
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
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
