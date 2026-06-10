export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
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
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/timeline");
  }

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
    <AppShell>
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Timeline</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Program phases and subsystem progress across the NPI schedule.
          </p>
        </div>

        {timeline ? (
          <TimelineBoard timeline={timeline} />
        ) : (
          <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-white p-8 text-center">
            <p className="text-sm font-medium text-[var(--text-primary)]">No timeline yet.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Once a project exists, its phase plan and subsystem lanes show here.
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
