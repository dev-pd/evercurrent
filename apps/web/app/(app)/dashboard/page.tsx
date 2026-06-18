export const dynamic = "force-dynamic";

import { cookies } from "next/headers";
import { apiServer, VIEW_AS_COOKIE } from "@/lib/api";
import { ContextBar } from "@/components/dashboard/context-bar";
import { DigestColumns } from "@/components/dashboard/digest-columns";
import { EmptyState } from "@/components/ui/empty-state";
import { parseDigest } from "@/lib/digest-parse";
import { messages } from "@/lib/messages";
import type { DigestV2, MemberSummary } from "@/lib/types";

const copy = messages.dashboard;

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

export default async function DashboardPage() {
  const asMember = (await cookies()).get(VIEW_AS_COOKIE)?.value ?? null;
  const client = await apiServer();

  const [members, projects, digest] = await Promise.all([
    safeFetch<MemberSummary[]>(() => client.listMembers()),
    safeFetch(() => client.listProjects()),
    safeFetch<DigestV2>(() => client.getDigestToday()),
  ]);

  const memberList = members ?? [];
  const currentMember =
    memberList.find((member) => member.id === asMember) ?? memberList[0] ?? null;
  const projectId = projects?.[0]?.id ?? null;

  const [today, timeline, openSignalPage] = await Promise.all([
    projectId ? safeFetch(() => client.getToday(projectId)) : Promise.resolve(null),
    projectId ? safeFetch(() => client.getTimeline(projectId)) : Promise.resolve(null),
    projectId
      ? safeFetch(() => client.listSignals({ projectId, status: "open", limit: 1 }))
      : Promise.resolve(null),
  ]);

  const buckets = parseDigest(digest?.content_md);

  const phase = today?.phase ?? digest?.phase ?? "—";
  const dayIndex = today?.live_day ?? digest?.day_index ?? 0;

  const openSignals = openSignalPage?.total ?? 0;
  const fcsTarget = timeline?.fcs_label?.split(" FCS")[0] ?? "—";

  const kpis = [
    { label: copy.kpiMessagesToday, value: today?.message_count ?? 0 },
    { label: copy.kpiProgramProgress, value: `${timeline?.progress_pct ?? 0}%` },
    { label: copy.kpiFcsTarget, value: fcsTarget },
    { label: copy.kpiOpenSignals, value: openSignals },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-[var(--border-default)] px-4 py-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <ContextBar
            currentMember={currentMember}
            phase={phase}
            dayIndex={dayIndex}
            projectId={projectId}
            generatedAt={digest?.generated_at ?? null}
            kpis={kpis}
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
          {digest === null ? (
            <EmptyState title={copy.noDigestTitle} hint={copy.noDigestHint} />
          ) : (
            <DigestColumns buckets={buckets} />
          )}
        </div>
      </div>
    </div>
  );
}
