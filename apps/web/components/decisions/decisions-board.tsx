"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { DataTable, type Column } from "@/components/ui/data-table";
import { useEvents } from "@/hooks/use-events";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import type { SignalListItem } from "@/lib/types";
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

const kindColumn: Column<SignalListItem> = {
  key: "kind",
  header: "Kind",
  sortValue: (c) => c.kind,
  render: (c) => (
    <span
      className={`inline-block rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase ${kindStyle(c.kind)}`}
    >
      {c.kind}
    </span>
  ),
};

const sourcesColumn: Column<SignalListItem> = {
  key: "sources",
  header: "Sources",
  sortValue: (c) => c.sources_count,
  render: (c) => (
    <span className="inline-flex items-center gap-1 text-xs">
      <MessageSquare className="h-3 w-3" aria-hidden="true" />
      {c.sources_count}
    </span>
  ),
};

const summaryColumn: Column<SignalListItem> = {
  key: "summary",
  header: "Summary",
  className: "w-[55%]",
  sortValue: (c) => c.summary.toLowerCase(),
  render: (c) => <span className="font-medium text-[var(--text-primary)]">{c.summary}</span>,
};

const statusColumn: Column<SignalListItem> = {
  key: "status",
  header: "Status",
  sortValue: (c) => c.status,
  render: (c) => <span className="font-mono text-xs tracking-wider uppercase">{c.status}</span>,
};

const resolvedColumn: Column<SignalListItem> = {
  key: "resolved",
  header: "Resolved",
  sortValue: (c) => c.resolved_at ?? "",
  render: (c) => {
    const date = formatTimestamp(c.resolved_at, "date");
    return (
      <span className="text-xs whitespace-nowrap text-[var(--text-muted)]">
        {date ? copy.resolvedSince(date) : "—"}
      </span>
    );
  },
};

const openColumns: Column<SignalListItem>[] = [
  kindColumn,
  summaryColumn,
  statusColumn,
  sourcesColumn,
];

const resolvedColumns: Column<SignalListItem>[] = [
  kindColumn,
  summaryColumn,
  resolvedColumn,
  sourcesColumn,
];

type Filter =
  | { key: "mine" }
  | { key: "all" }
  | { key: "open" }
  | { key: "resolved" }
  | { key: "kind"; kind: "decision" | "risk" | "question" };

function buildFilters(hasSubs: boolean): { label: string; filter: Filter }[] {
  return [
    ...(hasSubs ? [{ label: copy.filterMine, filter: { key: "mine" } as Filter }] : []),
    { label: copy.filterAllOpen, filter: { key: "open" } },
    { label: copy.filterDecisions, filter: { key: "kind", kind: "decision" } },
    { label: copy.filterRisks, filter: { key: "kind", kind: "risk" } },
    { label: copy.filterQuestions, filter: { key: "kind", kind: "question" } },
    { label: copy.filterResolved, filter: { key: "resolved" } },
    { label: copy.filterAll, filter: { key: "all" } },
  ];
}

function inMyScope(signal: SignalListItem, mySubs: string[]): boolean {
  if (signal.status !== "open") return false;
  if (mySubs.length === 0) return true;
  return signal.affected_subsystems.some((subsystem) => mySubs.includes(subsystem));
}

function matches(signal: SignalListItem, f: Filter, mySubs: string[]): boolean {
  if (f.key === "all") return true;
  if (f.key === "open") return signal.status === "open";
  if (f.key === "resolved") return signal.status === "resolved";
  if (f.key === "kind") return signal.status === "open" && signal.kind === f.kind;
  return inMyScope(signal, mySubs);
}

function isActive(a: Filter, b: Filter): boolean {
  if (a.key !== b.key) return false;
  if (a.key === "kind" && b.key === "kind") return a.kind === b.kind;
  return true;
}

export function DecisionsBoard({
  signals,
  mySubsystems = [],
  projectId = null,
}: {
  signals: SignalListItem[];
  mySubsystems?: string[];
  projectId?: string | null;
}) {
  // Live updates: signal_created / signal_resolved refresh the server tree so
  // the board fills in as signals generate (handled in the use-events switch).
  useEvents({ projectId, enabled: !!projectId });
  const hasSubs = mySubsystems.length > 0;
  const filters = buildFilters(hasSubs);
  const [filter, setFilter] = useState<Filter>(hasSubs ? { key: "mine" } : { key: "open" });
  const filtered = signals.filter((signal) => matches(signal, filter, mySubsystems));
  const open = useDecisionModal((s) => s.open);
  const columns = filter.key === "resolved" ? resolvedColumns : openColumns;

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
          {filtered.length}/{signals.length}
        </span>
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(c) => c.id}
        onRowClick={(c) => open(c.id)}
        emptyLabel={copy.noMatch}
      />
    </div>
  );
}
