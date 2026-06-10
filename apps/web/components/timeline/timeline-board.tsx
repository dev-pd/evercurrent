import { Plane } from "lucide-react";
import type { Timeline } from "@/lib/types";
import { DayMarker } from "./day-marker";
import { LaneRow } from "./lane-row";
import { PhaseBadge } from "./phase-badge";

interface TimelineBoardProps {
  timeline: Timeline;
}

export function TimelineBoard({ timeline }: TimelineBoardProps) {
  const span = timeline.months.length;
  const currentMonth = timeline.current_day / 30;
  const markerPct = (currentMonth / span) * 100;
  const cols = { gridTemplateColumns: `repeat(${span}, minmax(0, 1fr))` };

  return (
    <section className="overflow-hidden rounded-xl border border-[var(--border-default)] bg-white">
      <header className="flex items-center justify-between border-b border-[var(--border-default)] px-5 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Plane className="h-4 w-4 text-[var(--color-accent-600)]" aria-hidden="true" />
          {timeline.project_name}
        </div>
        <span className="text-[11px] text-[var(--text-muted)]">{timeline.fcs_label}</span>
      </header>

      <div className="px-5 pb-5 pt-4">
        <p className="mb-4 text-xs text-[var(--text-secondary)]">{timeline.summary}</p>

        <div className="relative">
          <div
            className="grid border-b border-[var(--border-default)] pb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]"
            style={cols}
          >
            {timeline.months.map((m, idx) => (
              <div key={`${m}-${idx}`} className="text-center">
                {m}
              </div>
            ))}
          </div>

          <div className="relative mt-2 grid gap-0" style={cols}>
            {timeline.phases.map((p) => (
              <PhaseBadge key={p.label} phase={p} span={span} />
            ))}
          </div>

          <div className="relative mt-6 flex flex-col gap-3">
            {timeline.lanes.map((lane) => (
              <LaneRow key={lane.name} lane={lane} span={span} />
            ))}
          </div>

          <DayMarker leftPct={markerPct} />
        </div>
      </div>
    </section>
  );
}
