export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
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
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Insights</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Proactive changes Eve detected across requirements, specs, and their downstream impact.
          </p>
        </div>

        {insights.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">No insights yet.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Eve surfaces requirement changes and cross-subsystem conflicts here as they appear.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
