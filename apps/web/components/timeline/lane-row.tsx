import type { TimelineLane } from "@/lib/types";

interface LaneRowProps {
  lane: TimelineLane;
  span: number;
}

export function LaneRow({ lane, span }: LaneRowProps) {
  return (
    <div className="relative">
      <div className="flex items-center gap-3">
        <span className="w-20 text-[11px] font-medium text-[var(--text-secondary)]">
          {lane.name}
        </span>
        <div className="relative h-2 flex-1 rounded-full bg-[var(--surface-muted)]">
          {lane.segments.map((seg, idx) => {
            const left = (seg.start / span) * 100;
            const width = ((seg.end - seg.start) / span) * 100;
            return (
              <div
                key={idx}
                className={`absolute top-0 bottom-0 rounded-full ${
                  seg.tone === "primary"
                    ? "bg-[var(--color-accent-600)]"
                    : "bg-[var(--color-accent-200)]"
                }`}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            );
          })}
          <div
            className="absolute -top-1.5 h-5 w-5 -translate-x-1/2 rounded-full border-2 border-[var(--color-accent-600)] bg-white"
            style={{ left: `${(lane.marker / span) * 100}%` }}
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
}
