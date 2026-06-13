export const dynamic = "force-dynamic";

import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { TimelineBoard } from "@/components/timeline/timeline-board";
import type { Timeline } from "@/lib/types";

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

  const timeline = projectId
    ? await safeFetch<Timeline>(() => client.getTimeline(projectId))
    : null;

  return (
    <PageContainer>
      <PageHeader
        title="Timeline"
        subtitle="Program phases and subsystem progress across the NPI schedule."
      />

      {timeline ? (
        <TimelineBoard timeline={timeline} />
      ) : (
        <EmptyState
          title="No timeline yet."
          hint="Once a project exists, its phase plan and subsystem lanes show here."
        />
      )}
    </PageContainer>
  );
}
