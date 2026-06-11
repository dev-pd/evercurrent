export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { InsightCard } from "@/components/insights/insight-card";
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
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/insights");
  }

  const client = await apiServer();
  const insights = (await safeFetch<ProactiveInsight[]>(() => client.getInsights(10))) ?? [];

  return (
    <AppShell>
      <PageContainer>
        <PageHeader
          title="Insights"
          subtitle="Proactive changes Eve detected across requirements, specs, and downstream impact."
        />

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
    </AppShell>
  );
}
