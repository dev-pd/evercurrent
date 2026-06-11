import { Sparkles, GitBranch } from "lucide-react";

/**
 * Always-on right rail: Eve proactive insights + cross-role alerts. Generation
 * isn't wired yet, so this shows the structure + empty states for now.
 */
export function EveRail() {
  return (
    <aside className="hidden w-72 shrink-0 flex-col border-l border-[var(--border-default)] bg-white xl:flex">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border-default)] px-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-[var(--text-primary)]">Eve</span>
          <span className="text-[11px] text-[var(--text-muted)]">Proactive insights</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <section>
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Cross-team changes
          </h3>
          <div className="mt-2 rounded-lg border border-dashed border-[var(--border-default)] px-3 py-6 text-center text-xs text-[var(--text-muted)]">
            No active insights. Eve flags spec/decision changes that ripple across
            subsystems here.
          </div>
        </section>

        <section className="mt-5">
          <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <GitBranch className="h-3 w-3" aria-hidden="true" />
            Cross-role alerts
          </h3>
          <div className="mt-2 rounded-lg border border-dashed border-[var(--border-default)] px-3 py-6 text-center text-xs text-[var(--text-muted)]">
            Dependencies that touch your subsystems will surface here.
          </div>
        </section>
      </div>
    </aside>
  );
}
