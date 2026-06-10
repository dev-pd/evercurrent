import { Sparkles } from "lucide-react";
import type { ProactiveInsight } from "@/lib/types";
import { ConflictList } from "./conflict-list";
import { ImpactSummary } from "./impact-summary";
import { InsightSources } from "./insight-sources";
import { SpecDiff } from "./spec-diff";
import { SuggestedActionBar } from "./suggested-action-bar";

interface InsightCardProps {
  insight: ProactiveInsight;
}

function formatDetectedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function InsightCard({ insight }: InsightCardProps) {
  return (
    <article className="overflow-hidden rounded-xl border border-[var(--color-accent-200)] bg-gradient-to-br from-white to-[var(--color-accent-50)]">
      <header className="flex items-start gap-3 border-b border-[var(--color-accent-100)] px-5 py-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="flex flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[var(--color-accent-700)]">
            <span className="font-semibold">Eve</span>
            <span aria-hidden="true">·</span>
            <span className="font-mono">{insight.req_id}</span>
            <span aria-hidden="true">·</span>
            <span>detected {formatDetectedAt(insight.detected_at)}</span>
          </div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{insight.title}</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{insight.summary}</p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 px-5 py-5 sm:grid-cols-2">
        <SpecDiff label="Before" specs={insight.before} tone="before" />
        <SpecDiff label="After" specs={insight.after} tone="after" />
      </div>

      <ConflictList
        conflicts={insight.conflicts}
        affectedSubsystems={insight.affected_subsystems}
      />
      <ImpactSummary impact={insight.impact_summary} />
      <InsightSources sources={insight.sources} />
      <SuggestedActionBar action={insight.suggested_action} />
    </article>
  );
}
