export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { InsightsView } from "@/components/insights/insights-view";
import { GenerateInsightButton } from "@/components/insights/generate-insight-button";
import { messages } from "@/lib/messages";
import type { ProactiveInsight, Project, TodayV2 } from "@/lib/types";

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
  const today = projectId
    ? await safeFetch<TodayV2>(() => client.getToday(projectId))
    : null;
  const hasData = today?.last_message_at != null;

  return (
    <PageContainer
      header={
        <PageHeader
          title={copy.title}
          subtitle={copy.subtitle}
          action={<GenerateInsightButton hasData={hasData} />}
        />
      }
    >
      <InsightsView insights={insightList} />
    </PageContainer>
  );
}
