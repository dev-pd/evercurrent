"use client";

import { AlertTriangle } from "lucide-react";
import { timeAgo } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import type { CardListItem } from "@/lib/types";
import { useDecisionModal } from "@/stores/decision-modal";

const copy = messages.timeline;

export function BlockerBoard({ cards, limit = 8 }: { cards: CardListItem[]; limit?: number }) {
  const open = useDecisionModal((s) => s.open);
  const blockers = cards
    .filter((card) => card.kind === "risk" && card.status === "open")
    .sort((left, right) => (right.occurred_at ?? "").localeCompare(left.occurred_at ?? ""))
    .slice(0, limit);

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-[var(--border-default)] bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <AlertTriangle className="h-4 w-4 text-amber-500" /> {copy.blockersHeading}
        </h3>
        <span className="font-mono text-xs text-[var(--text-muted)] tabular-nums">
          {blockers.length}
        </span>
      </div>

      {blockers.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{copy.blockersEmpty}</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {blockers.map((blocker) => (
            <button
              key={blocker.id}
              type="button"
              onClick={() => open(blocker.id)}
              className="group flex flex-col gap-2 rounded-md border border-[var(--border-default)] p-3 text-left transition-colors hover:border-[var(--color-accent-300)] hover:bg-[var(--surface-muted)]"
            >
              <div className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500" />
                <p className="line-clamp-3 text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--color-accent-700)]">
                  {blocker.summary}
                </p>
              </div>
              <div className="mt-auto flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                {blocker.affected_subsystems.slice(0, 3).map((subsystem) => (
                  <span
                    key={subsystem}
                    className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[var(--text-secondary)]"
                  >
                    {subsystem}
                  </span>
                ))}
                <span className="ml-auto tabular-nums">{timeAgo(blocker.occurred_at)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
