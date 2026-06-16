export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { GanttChart } from "@/components/timeline/gantt-chart";
import { BlockerBoard } from "@/components/timeline/blocker-board";
import { messages } from "@/lib/messages";
import type { CardListItem, Timeline } from "@/lib/types";

const copy = messages.timeline;

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("timeline fetch failed", error);
    }
    return null;
  }
}

interface TimelinePageProps {
  searchParams: Promise<{ project_id?: string }>;
}

export default async function TimelinePage({ searchParams }: TimelinePageProps) {
  const params = await searchParams;
  const client = await apiServer();

  let projectId = params.project_id ?? null;
  if (!projectId) {
    const projects = await safeFetch(() => client.listProjects());
    projectId = projects?.[0]?.id ?? null;
  }

  const [timeline, cards] = projectId
    ? await Promise.all([
        safeFetch<Timeline>(() => client.getTimeline(projectId)),
        safeFetch<CardListItem[]>(() => client.listCards({ limit: 1000 })),
      ])
    : [null, null];
  const cardList = cards ?? [];

  return (
    <PageContainer header={<PageHeader title={copy.title} subtitle={copy.subtitle} />}>
      {timeline ? (
        <>
          <GanttChart
            startDate={timeline.start_date}
            fcsLabel={timeline.fcs_label}
            cards={cardList}
          />
          <BlockerBoard cards={cardList} />
        </>
      ) : (
        <EmptyState title={copy.emptyTitle} hint={copy.emptyHint} />
      )}
    </PageContainer>
  );
}
