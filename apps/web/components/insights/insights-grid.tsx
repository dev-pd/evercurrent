"use client";

import { AlertTriangle, Sparkles } from "lucide-react";
import { formatTimestamp } from "@/lib/format-date";
import type { ProactiveInsight } from "@/lib/types";
import { useInsightModal } from "@/stores/insight-modal";
import { InsightModal } from "./insight-modal";

interface InsightsGridProps {
  insights: ProactiveInsight[];
}

export function InsightsGrid({ insights }: InsightsGridProps) {
  const open = useInsightModal((s) => s.open);

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {insights.map((insight) => (
          <button
            key={insight.id}
            type="button"
            onClick={() => open(insight)}
            className="group flex flex-col gap-2 rounded-xl border border-[var(--border-default)] bg-white p-4 text-left transition-colors hover:border-[var(--color-accent-300)] hover:shadow-sm"
          >
            <div className="flex items-center gap-2 text-[11px] tracking-wider text-[var(--color-accent-700)] uppercase">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="font-mono">{insight.req_id}</span>
            </div>
            <h3 className="line-clamp-2 text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--color-accent-700)]">
              {insight.title}
            </h3>
            <p className="line-clamp-2 text-xs text-[var(--text-secondary)]">{insight.summary}</p>
            <div className="mt-auto flex flex-wrap items-center gap-3 pt-1 text-[11px] text-[var(--text-muted)]">
              <span>{formatTimestamp(insight.detected_at) ?? insight.detected_at}</span>
              {insight.conflicts.length > 0 && (
                <span className="inline-flex items-center gap-1 text-amber-600">
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  {insight.conflicts.length}
                </span>
              )}
              {insight.affected_subsystems.slice(0, 2).map((subsystem) => (
                <span
                  key={subsystem}
                  className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-[10px]"
                >
                  {subsystem}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>
      <InsightModal />
    </>
  );
}
