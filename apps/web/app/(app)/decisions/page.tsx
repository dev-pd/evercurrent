export const dynamic = "force-dynamic";

import { cookies } from "next/headers";
import { apiServer, VIEW_AS_COOKIE } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { DecisionsBoard } from "@/components/decisions/decisions-board";
import type { CardListItem, MemberSummary } from "@/lib/types";

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
  const [cards, members] = await Promise.all([
    safe<CardListItem[]>(() => client.listCards({ limit: 1000 }), []),
    safe<MemberSummary[]>(() => client.listMembers(), []),
  ]);

  const viewedId = (await cookies()).get(VIEW_AS_COOKIE)?.value ?? null;
  const viewed = members.find((m) => m.id === viewedId) ?? members[0] ?? null;
  const mySubsystems = viewed?.owned_subsystems ?? [];

  const subtitle = viewed
    ? `Open decisions, risks, and questions for ${viewed.display_name}'s subsystems — switch the full log below.`
    : "Structured decisions, risks, and questions extracted from team chatter and docs.";

  return (
    <PageContainer header={<PageHeader title="Decisions" subtitle={subtitle} />}>
      <DecisionsBoard cards={cards} mySubsystems={mySubsystems} />
    </PageContainer>
  );
}
