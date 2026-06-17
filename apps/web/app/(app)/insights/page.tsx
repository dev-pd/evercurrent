export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { InsightsTable } from "@/components/insights/insights-table";
import { GenerateInsightButton } from "@/components/insights/generate-insight-button";
import { messages } from "@/lib/messages";
import type { ProactiveInsight, Project } from "@/lib/types";

const copy = messages.insights;

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
  const [insights, projects] = await Promise.all([
    safeFetch<ProactiveInsight[]>(() => client.getInsights(1000)),
    safeFetch<Project[]>(() => client.listProjects()),
  ]);
  const insightList = insights ?? [];
  const projectId = projects?.[0]?.id ?? null;

  return (
    <PageContainer
      header={
        <PageHeader
          title={copy.title}
          subtitle={copy.subtitle}
          action={<GenerateInsightButton projectId={projectId} />}
        />
      }
    >
      {insightList.length === 0 ? (
        <EmptyState title={copy.emptyTitle} hint={copy.emptyHint} />
      ) : (
        <InsightsTable insights={insightList} />
      )}
    </PageContainer>
  );
}
