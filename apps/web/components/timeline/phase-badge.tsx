import type { TimelinePhase } from "@/lib/types";

interface PhaseBadgeProps {
  phase: TimelinePhase;
  span: number;
}

const STATUS_TONE: Record<TimelinePhase["status"], string> = {
  done: "border-zinc-200 bg-zinc-50 text-zinc-600",
  active:
    "border-[var(--color-accent-300)] bg-[var(--color-accent-100)] text-[var(--color-accent-800)]",
  upcoming: "border-zinc-200 bg-white text-zinc-500",
};

export function PhaseBadge({ phase, span }: PhaseBadgeProps) {
  const left = (phase.start_month / span) * 100;
  const width = ((phase.end_month - phase.start_month) / span) * 100;
  return (
    <div
      className={`absolute rounded-md border px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase ${STATUS_TONE[phase.status]}`}
      style={{ left: `${left}%`, width: `${width}%` }}
    >
      <span className="block truncate text-center">{phase.label}</span>
    </div>
  );
}
