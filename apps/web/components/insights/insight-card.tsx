import { Sparkles } from "lucide-react";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import type { ProactiveInsight } from "@/lib/types";
import { ConflictList } from "./conflict-list";
import { ImpactSummary } from "./impact-summary";
import { InsightSources } from "./insight-sources";
import { SpecDiff } from "./spec-diff";
import { SuggestedActionBar } from "./suggested-action-bar";

const copy = messages.insights;

interface InsightCardProps {
  insight: ProactiveInsight;
}

export function InsightCard({ insight }: InsightCardProps) {
  return (
    <article className="glass-strong glass-sheen overflow-hidden rounded-xl border border-[var(--glass-border)]">
      <header className="flex items-start gap-3 border-b border-[var(--color-accent-100)] px-5 py-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="flex flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2 text-[11px] tracking-wider text-[var(--color-accent-700)] uppercase">
            <span className="font-semibold">{copy.eveAuthor}</span>
            <span aria-hidden="true">·</span>
            <span className="font-mono">{insight.req_id}</span>
            <span aria-hidden="true">·</span>
            <span>
              {copy.detectedPrefix} {formatTimestamp(insight.detected_at) ?? insight.detected_at}
            </span>
          </div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{insight.title}</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{insight.summary}</p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 px-5 py-5 sm:grid-cols-2">
        <SpecDiff label={copy.before} specs={insight.before} tone="before" />
        <SpecDiff label={copy.after} specs={insight.after} tone="after" />
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
