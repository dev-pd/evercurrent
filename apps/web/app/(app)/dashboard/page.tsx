export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { ContextBar } from "@/components/dashboard/context-bar";
import { FocusPanel } from "@/components/dashboard/focus-panel";
import { DigestColumns } from "@/components/dashboard/digest-columns";
import { AnomalyBanner } from "@/components/dashboard/anomaly-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { parseDigest } from "@/lib/digest-parse";
import type { DigestV2, MemberSummary } from "@/lib/types";

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
  const params = await searchParams;
  const asMember = params.as ?? null;
  const client = await apiServer(asMember);

  const [members, projects, digest] = await Promise.all([
    safeFetch<MemberSummary[]>(() => client.listMembers()),
    safeFetch(() => client.listProjects()),
    safeFetch<DigestV2>(() => client.getDigestToday()),
  ]);

  const memberList = members ?? [];
  const currentMember = memberList.find((m) => m.id === asMember) ?? memberList[0] ?? null;
  const projectId = projects?.[0]?.id ?? null;

  const [today, timeline, cards, focus] = await Promise.all([
    projectId ? safeFetch(() => client.getToday(projectId)) : Promise.resolve(null),
    projectId ? safeFetch(() => client.getTimeline(projectId)) : Promise.resolve(null),
    projectId ? safeFetch(() => client.listCards({ projectId })) : Promise.resolve(null),
    safeFetch(() => client.getFocus()),
  ]);

  const buckets = parseDigest(digest?.content_md);

  const phase = digest?.phase ?? "—";
  const dayIndex = digest?.day_index ?? 0;
  const summary = buildSummary(buckets.top_priority.length, currentMember?.display_name ?? "there");

  const openDecisions = (cards ?? []).filter((c) => c.status === "open").length;
  const fcsTarget = timeline?.fcs_label?.split(" FCS")[0] ?? "—";

  const kpis = [
    { label: "Signals today", value: today?.message_count ?? 0 },
    { label: "Program progress", value: `${timeline?.progress_pct ?? 0}%`, hint: phase },
    { label: "FCS target", value: fcsTarget },
    { label: "Open decisions", value: openDecisions },
  ];

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-4">
      <ContextBar
        currentMember={currentMember}
        phase={phase}
        dayIndex={dayIndex}
        summary={summary}
        projectId={projectId}
        generatedAt={digest?.generated_at ?? null}
        kpis={kpis}
      />

      <FocusPanel focus={focus ?? []} />

      <AnomalyBanner anomalies={digest?.anomalies ?? []} />

      {digest === null ? (
        <EmptyState
          title="No digest yet."
          hint="Connect Slack and regenerate to draft the first briefing."
        />
      ) : (
        <DigestColumns buckets={buckets} />
      )}
    </div>
  );
}
