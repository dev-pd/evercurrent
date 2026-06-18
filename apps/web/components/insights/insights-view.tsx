"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { InsightsTable } from "@/components/insights/insights-table";
import { messages } from "@/lib/messages";
import { useEve } from "@/stores/eve";
import type { ProactiveInsight } from "@/lib/types";

const copy = messages.insights;

export function InsightsView({ insights }: { insights: ProactiveInsight[] }) {
  const running = useEve((s) => s.running);

  if (insights.length === 0) {
    if (running) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-12">
          <Spinner size="md" />
          <span className="text-sm text-[var(--text-muted)]">{copy.eveInvestigating}</span>
        </div>
      );
    }
    return <EmptyState title={copy.emptyTitle} hint={copy.emptyHint} />;
  }

  return <InsightsTable insights={insights} />;
}
