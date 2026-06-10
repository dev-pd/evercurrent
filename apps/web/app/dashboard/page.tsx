export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { DigestHeader } from "@/components/dashboard/digest-header";
import { DigestSection } from "@/components/dashboard/digest-section";
import { AnomalyBanner } from "@/components/dashboard/anomaly-banner";
import { LiveUpdatesBadge } from "@/components/dashboard/live-updates-badge";
import { MetricStrip } from "@/components/dashboard/metric-strip";
import type { DigestV2, TodayV2 } from "@/lib/types";

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("dashboard fetch failed", error);
    }
    return null;
  }
}

interface DashboardPageProps {
  searchParams: Promise<{ project_id?: string }>;
}

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/dashboard");
  }

  const params = await searchParams;
  const projectId = params.project_id ?? null;
  const client = await apiServer();

  const [today, digest] = await Promise.all([
    projectId ? safeFetch<TodayV2>(() => client.getToday(projectId)) : Promise.resolve(null),
    safeFetch<DigestV2>(() => client.getDigestToday()),
  ]);

  const projectName = today ? `Project ${today.project_id.slice(0, 8)}` : "No project";
  const phase = today?.phase ?? digest?.phase ?? "—";
  const dayIndex = today?.live_day ?? digest?.day_index ?? 0;
  const generatedAt = digest?.generated_at ?? today?.last_digest_generated_at ?? null;

  const items = digest?.items ?? [];
  const topPriority = items.filter((i) => i.bucket === "top_priority");
  const watchOuts = items.filter((i) => i.bucket === "watch_outs");
  const fyi = items.filter((i) => i.bucket === "fyi");

  return (
    <AppShell>
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <DigestHeader
          projectName={projectName}
          phase={phase}
          dayIndex={dayIndex}
          generatedAt={generatedAt}
        />

        <MetricStrip
          signals={today?.message_count ?? items.length}
          decisions={topPriority.length}
          risks={watchOuts.length}
          docs={fyi.length}
        />

        <div className="flex items-center justify-between">
          <LiveUpdatesBadge projectId={projectId} generatedAt={generatedAt} />
        </div>

        <AnomalyBanner anomalies={digest?.anomalies ?? []} />

        {digest === null && (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">
              No digest yet.
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Connect Slack or Dropbox and click regenerate to draft your first briefing.
            </p>
          </div>
        )}

        {digest !== null && items.length === 0 && (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">
              Quiet day.
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              No signals scored above the threshold. Either the team didn&apos;t post
              much, or nothing is relevant to your subscriptions.
            </p>
          </div>
        )}

        <DigestSection bucket="top_priority" items={topPriority} />
        <DigestSection bucket="watch_outs" items={watchOuts} />
        <DigestSection bucket="fyi" items={fyi} />
      </div>
    </AppShell>
  );
}
