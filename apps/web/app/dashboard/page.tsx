import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { DigestHeader } from "@/components/dashboard/digest-header";
import { DigestSection } from "@/components/dashboard/digest-section";
import { AnomalyBanner } from "@/components/dashboard/anomaly-banner";
import { LiveUpdatesBadge } from "@/components/dashboard/live-updates-badge";
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

  const projectName = today ? `Project ${today.project_id.slice(0, 8)}` : "Your project";
  const phase = today?.phase ?? digest?.phase ?? "—";
  const dayIndex = today?.live_day ?? digest?.day_index ?? 0;
  const generatedAt = digest?.generated_at ?? today?.last_digest_at ?? null;

  const items = digest?.items ?? [];
  const topPriority = items.filter((i) => i.bucket === "top_priority");
  const watchOuts = items.filter((i) => i.bucket === "watch_outs");
  const fyi = items.filter((i) => i.bucket === "fyi");

  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <DigestHeader
          projectName={projectName}
          phase={phase}
          dayIndex={dayIndex}
          generatedAt={generatedAt}
        />

        <div className="flex items-center justify-between">
          <LiveUpdatesBadge projectId={projectId} generatedAt={generatedAt} />
        </div>

        {digest === null && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-500">
            No digest yet. Regenerate to draft your first briefing.
          </div>
        )}

        <DigestSection bucket="top_priority" items={topPriority} />
        <DigestSection bucket="watch_outs" items={watchOuts} />
        <DigestSection bucket="fyi" items={fyi} />

        <AnomalyBanner anomalies={digest?.anomalies ?? []} />
      </div>
    </AppShell>
  );
}
