"use client";

import { AlertTriangle } from "lucide-react";
import { formatTimestamp } from "@/lib/format-date";
import { DataTable, type Column } from "@/components/ui/data-table";
import type { ProactiveInsight } from "@/lib/types";
import { useInsightModal } from "@/stores/insight-modal";
import { InsightModal } from "./insight-modal";

const columns: Column<ProactiveInsight>[] = [
  {
    key: "title",
    header: "Insight",
    className: "w-[42%]",
    sortValue: (i) => i.title.toLowerCase(),
    render: (i) => (
      <div className="flex flex-col">
        <span className="font-medium text-[var(--text-primary)]">{i.title}</span>
        <span className="line-clamp-1 text-xs text-[var(--text-muted)]">{i.summary}</span>
      </div>
    ),
  },
  {
    key: "req_id",
    header: "Req",
    sortValue: (i) => i.req_id,
    render: (i) => <span className="font-mono text-xs">{i.req_id}</span>,
  },
  {
    key: "subsystems",
    header: "Subsystems",
    render: (i) => (
      <div className="flex flex-wrap gap-1">
        {i.affected_subsystems.slice(0, 3).map((subsystem) => (
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
    key: "conflicts",
    header: "Conflicts",
    sortValue: (i) => i.conflicts.length,
    render: (i) =>
      i.conflicts.length > 0 ? (
        <span className="inline-flex items-center gap-1 text-amber-600">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          {i.conflicts.length}
        </span>
      ) : (
        <span className="text-[var(--text-muted)]">—</span>
      ),
  },
  {
    key: "detected",
    header: "Detected",
    sortValue: (i) => i.detected_at,
    render: (i) => (
      <span className="text-xs whitespace-nowrap">
        {formatTimestamp(i.detected_at) ?? i.detected_at}
      </span>
    ),
  },
];

export function InsightsTable({ insights }: { insights: ProactiveInsight[] }) {
  const open = useInsightModal((s) => s.open);
  return (
    <>
      <DataTable
        columns={columns}
        rows={insights}
        rowKey={(i) => i.id}
        onRowClick={(i) => open(i)}
      />
      <InsightModal />
    </>
  );
}
