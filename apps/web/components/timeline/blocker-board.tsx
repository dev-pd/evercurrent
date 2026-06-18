"use client";

import { AlertTriangle } from "lucide-react";
import { timeAgo } from "@/lib/format-date";
import { DataTable, type Column } from "@/components/ui/data-table";
import { messages } from "@/lib/messages";
import type { SignalListItem } from "@/lib/types";
import { useDecisionModal } from "@/stores/decision-modal";

const copy = messages.timeline;

const columns: Column<SignalListItem>[] = [
  {
    key: "summary",
    header: "Blocker",
    className: "w-[55%]",
    sortValue: (c) => c.summary.toLowerCase(),
    render: (c) => (
      <span className="inline-flex items-start gap-2">
        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-500" />
        <span className="font-medium text-[var(--text-primary)]">{c.summary}</span>
      </span>
    ),
  },
  {
    key: "subsystems",
    header: "Subsystems",
    render: (c) => (
      <div className="flex flex-wrap gap-1">
        {c.affected_subsystems.slice(0, 3).map((subsystem) => (
          <span
            key={subsystem}
            className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-[10px]"
          >
            {subsystem}
          </span>
        ))}
      </div>
    ),
  },
  {
    key: "age",
    header: "Age",
    sortValue: (c) => c.occurred_at ?? "",
    render: (c) => (
      <span className="text-xs whitespace-nowrap tabular-nums">{timeAgo(c.occurred_at)}</span>
    ),
  },
];

export function BlockerBoard({ signals }: { signals: SignalListItem[] }) {
  const open = useDecisionModal((s) => s.open);
  const blockers = signals
    .filter((signal) => signal.kind === "risk" && signal.status === "open")
    .sort((left, right) => (right.occurred_at ?? "").localeCompare(left.occurred_at ?? ""));

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <AlertTriangle className="h-4 w-4 text-amber-500" /> {copy.blockersHeading}
        </h3>
        <span className="font-mono text-xs text-[var(--text-muted)] tabular-nums">
          {blockers.length}
        </span>
      </div>
      <DataTable
        columns={columns}
        rows={blockers}
        rowKey={(c) => c.id}
        onRowClick={(c) => open(c.id)}
        emptyLabel={copy.blockersEmpty}
      />
    </section>
  );
}
