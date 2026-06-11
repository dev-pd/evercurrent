export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { ContextBar } from "@/components/dashboard/context-bar";
import { DigestColumns } from "@/components/dashboard/digest-columns";
import { AnomalyBanner } from "@/components/dashboard/anomaly-banner";
import { LiveUpdatesBadge } from "@/components/dashboard/live-updates-badge";
import type { DigestItemV2, DigestV2, MemberSummary } from "@/lib/types";

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
  searchParams: Promise<{ as?: string }>;
}

function buildSummary(topCount: number, name: string): string {
  if (topCount === 0) return `You're caught up, ${name.split(" ")[0]}. Nothing needs you today.`;
  const noun = topCount === 1 ? "thing needs" : "things need";
  return `${topCount} ${noun} you today.`;
}

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/dashboard");
  }

  const params = await searchParams;
  const asMember = params.as ?? null;
  const client = await apiServer(asMember);

  const [members, projects, digest] = await Promise.all([
    safeFetch<MemberSummary[]>(() => client.listMembers()),
    safeFetch(() => client.listProjects()),
    safeFetch<DigestV2>(() => client.getDigestToday()),
  ]);

  const memberList = members ?? [];
  const currentMember =
    memberList.find((m) => m.id === asMember) ?? memberList[0] ?? null;
  const projectId = projects?.[0]?.id ?? null;

  const items: DigestItemV2[] = digest?.items ?? [];
  const buckets = {
    top_priority: items.filter((i) => i.bucket === "top_priority"),
    watch_outs: items.filter((i) => i.bucket === "watch_outs"),
    fyi: items.filter((i) => i.bucket === "fyi"),
  };

  const phase = digest?.phase ?? "—";
  const dayIndex = digest?.day_index ?? 0;
  const summary = buildSummary(buckets.top_priority.length, currentMember?.display_name ?? "there");

  return (
    <AppShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <ContextBar
          members={memberList}
          currentMember={currentMember}
          phase={phase}
          dayIndex={dayIndex}
          summary={summary}
        />

        <div className="flex items-center justify-between">
          <LiveUpdatesBadge projectId={projectId} generatedAt={digest?.generated_at ?? null} />
        </div>

        <AnomalyBanner anomalies={digest?.anomalies ?? []} />

        {digest === null ? (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">No digest yet.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Connect Slack and regenerate to draft the first briefing.
            </p>
          </div>
        ) : (
          <DigestColumns buckets={buckets} />
        )}
      </div>
    </AppShell>
  );
}
