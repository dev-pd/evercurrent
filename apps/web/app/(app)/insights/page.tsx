export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { InsightCard } from "@/components/insights/insight-card";
import { GenerateInsightButton } from "@/components/insights/generate-insight-button";
import { ChangeImpact3D } from "@/components/program/change-impact-3d";
import type { ProactiveInsight } from "@/lib/types";

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("insights fetch failed", error);
    }
    return null;
  }
}

export default async function InsightsPage() {
  const client = await apiServer();
  const insights = (await safeFetch<ProactiveInsight[]>(() => client.getInsights(10))) ?? [];

  const highlighted = insights[0]?.affected_subsystems ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="Insights"
        subtitle="Proactive changes Eve detected across requirements, specs, and downstream impact."
        action={<GenerateInsightButton />}
      />

      <ChangeImpact3D highlighted={highlighted} />

      {insights.length === 0 ? (
        <EmptyState
          title="No insights yet."
          hint="Eve surfaces requirement changes and cross-subsystem conflicts here as they appear."
        />
      ) : (
        <div className="flex flex-col gap-6">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
