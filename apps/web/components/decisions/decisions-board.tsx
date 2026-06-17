"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { messages } from "@/lib/messages";
import type { CardListItem } from "@/lib/types";
import { useDecisionModal } from "@/stores/decision-modal";

const copy = messages.decisions;

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
    ...(hasSubs ? [{ label: copy.filterMine, filter: { key: "mine" } as Filter }] : []),
    { label: copy.filterAllOpen, filter: { key: "open" } },
    { label: copy.filterDecisions, filter: { key: "kind", kind: "decision" } },
    { label: copy.filterRisks, filter: { key: "kind", kind: "risk" } },
    { label: copy.filterQuestions, filter: { key: "kind", kind: "question" } },
    { label: copy.filterAll, filter: { key: "all" } },
  ];
}

function inMyScope(card: CardListItem, mySubs: string[]): boolean {
  if (card.status !== "open") return false;
  if (mySubs.length === 0) return true;
  return card.affected_subsystems.some((subsystem) => mySubs.includes(subsystem));
}

function matches(card: CardListItem, f: Filter, mySubs: string[]): boolean {
  if (f.key === "all") return true;
  if (f.key === "open") return card.status === "open";
  if (f.key === "kind") return card.status === "open" && card.kind === f.kind;
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
  const filtered = cards.filter((card) => matches(card, filter, mySubsystems));
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
          <p className="text-sm font-medium text-[var(--text-primary)]">{copy.noMatch}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((card) => (
            <button
              key={card.id}
              type="button"
              onClick={() => open(card.id)}
              className="group flex flex-col gap-2 rounded-xl border border-[var(--border-default)] bg-white p-4 text-left transition-colors hover:border-[var(--color-accent-300)] hover:shadow-sm"
            >
              <span
                className={`w-[72px] rounded-md border py-0.5 text-center text-[10px] font-semibold tracking-wider uppercase ${kindStyle(card.kind)}`}
              >
                {card.kind}
              </span>
              <span className="line-clamp-3 text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--color-accent-700)]">
                {card.summary}
              </span>
              <div className="mt-auto flex flex-wrap items-center gap-3 pt-1 text-[11px] text-[var(--text-muted)]">
                <span className="font-mono tracking-wider uppercase">{card.status}</span>
                <span className="inline-flex items-center gap-1">
                  <MessageSquare className="h-3 w-3" aria-hidden="true" />
                  {card.sources_count}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
