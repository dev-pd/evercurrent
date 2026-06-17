import { messages } from "@/lib/messages";
import type { Project } from "@/lib/types";

const copy = messages.projects;

export function ProjectsCard({ projects }: { projects: Project[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">{copy.heading}</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
        {projects.length === 0 ? (
          <p className="p-4 text-xs text-[var(--text-muted)]">{copy.empty}</p>
        ) : (
          projects.map((project, i) => (
            <div
              key={project.id}
              className={`flex items-center justify-between gap-3 p-4 ${
                i > 0 ? "border-t border-[var(--border-default)]" : ""
              }`}
            >
              <span className="text-sm font-medium text-[var(--text-primary)]">{project.name}</span>
              <span className="inline-flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 font-medium uppercase">
                  {project.current_phase}
                </span>
                {copy.dayPrefix} {project.current_day}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
