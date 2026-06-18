export const dynamic = "force-dynamic";

import { cookies } from "next/headers";
import { apiServer, VIEW_AS_COOKIE } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { DecisionsBoard } from "@/components/decisions/decisions-board";
import { messages } from "@/lib/messages";
import type { SignalPage, MemberSummary, Project } from "@/lib/types";

const copy = messages.decisions;

async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("decisions fetch failed", error);
    }
    return fallback;
  }
}

export default async function DecisionsPage() {
  const client = await apiServer();
  const [signalPage, members, projects] = await Promise.all([
    safe<SignalPage | null>(() => client.listSignals({ limit: 1000 }), null),
    safe<MemberSummary[]>(() => client.listMembers(), []),
    safe<Project[]>(() => client.listProjects(), []),
  ]);
  const signals = signalPage?.items ?? [];
  const projectId = projects[0]?.id ?? null;

  const viewedId = (await cookies()).get(VIEW_AS_COOKIE)?.value ?? null;
  const viewed = members.find((member) => member.id === viewedId) ?? members[0] ?? null;
  const mySubsystems = viewed?.owned_subsystems ?? [];
  const myRole = viewed?.eng_role ?? null;

  const subtitle = viewed ? copy.subtitleScoped(viewed.display_name) : copy.subtitleDefault;

  return (
    <PageContainer header={<PageHeader title={copy.title} subtitle={subtitle} />}>
      <DecisionsBoard
        signals={signals}
        mySubsystems={mySubsystems}
        myRole={myRole}
        projectId={projectId}
      />
    </PageContainer>
  );
}
