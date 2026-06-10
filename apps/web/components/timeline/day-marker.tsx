interface DayMarkerProps {
  leftPct: number;
}

export function DayMarker({ leftPct }: DayMarkerProps) {
  return (
    <div
      className="pointer-events-none absolute top-0 bottom-0 border-l-2 border-dashed border-[var(--color-accent-500)]"
      style={{ left: `${leftPct}%` }}
      aria-hidden="true"
    >
      <span className="absolute -top-1 -translate-x-1/2 rounded-md bg-[var(--color-accent-600)] px-1.5 py-0.5 font-mono text-[10px] text-white">
        today
      </span>
    </div>
  );
}
