"use client";

import { useState } from "react";
import { Flag } from "lucide-react";
import type { CardListItem } from "@/lib/types";
import { useDecisionModal } from "@/stores/decision-modal";

const PHASES = [
  { key: "EVT", band: "bg-sky-100", label: "text-sky-700" },
  { key: "DVT", band: "bg-violet-100", label: "text-violet-700" },
  { key: "PVT", band: "bg-amber-100", label: "text-amber-700" },
  { key: "FCS", band: "bg-emerald-100", label: "text-emerald-700" },
] as const;

const KIND_DOT: Record<string, string> = {
  decision: "bg-emerald-500 ring-emerald-200",
  risk: "bg-amber-500 ring-amber-200",
  question: "bg-sky-500 ring-sky-200",
};

interface GanttProps {
  startDate: string;
  fcsLabel: string;
  cards: CardListItem[];
}

interface Marker {
  card: CardListItem;
  pct: number;
}

function fmt(d: Date): string {
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function GanttChart({ startDate, fcsLabel, cards }: GanttProps) {
  const open = useDecisionModal((s) => s.open);
  const [hover, setHover] = useState<Marker | null>(null);

  const start = new Date(startDate).getTime();
  // eslint-disable-next-line react-hooks/purity -- "today" marker intentionally reads wall-clock
  const now = Date.now();
  const span = Math.max(now - start, 1);
  const pct = (time: number) => Math.min(100, Math.max(0, ((time - start) / span) * 100));

  // Phases = 4 equal windows from start -> today (corpus was posted in phase order).
  const phaseBounds = PHASES.map((phase, i) => ({
    ...phase,
    left: (i / PHASES.length) * 100,
    width: 100 / PHASES.length,
  }));

  // Plot open decisions + risks by their real (backdated) date.
  const markers: Marker[] = cards
    .filter((card) => card.status === "open" && card.kind !== "question" && card.occurred_at)
    .map((card) => ({ card, pct: pct(new Date(card.occurred_at as string).getTime()) }));

  const ticks = Array.from({ length: 5 }, (_, i) => {
    const tickTime = start + (span * i) / 4;
    return { pct: (i / 4) * 100, label: fmt(new Date(tickTime)) };
  });

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--border-default)] bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Program timeline</h3>
        <span className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)]">
          <Flag className="h-3 w-3" /> {fcsLabel}
        </span>
      </div>

      <div className="relative h-9 w-full overflow-hidden rounded-md">
        {phaseBounds.map((phase) => (
          <div
            key={phase.key}
            className={`absolute top-0 flex h-full items-center justify-center ${phase.band}`}
            style={{ left: `${phase.left}%`, width: `${phase.width}%` }}
          >
            <span className={`text-[11px] font-semibold tracking-wider ${phase.label}`}>
              {phase.key}
            </span>
          </div>
        ))}
        <div
          className="absolute top-0 h-full w-0.5 bg-[var(--text-primary)]"
          style={{ left: "100%" }}
        />
      </div>

      {/* Decision / risk markers track */}
      <div className="relative h-10 w-full">
        <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-[var(--border-default)]" />
        {markers.map((marker, i) => (
          <button
            key={marker.card.id + i}
            type="button"
            onClick={() => open(marker.card.id)}
            onMouseEnter={() => setHover(marker)}
            onMouseLeave={() => setHover(null)}
            aria-label={marker.card.summary}
            className={`absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ${KIND_DOT[marker.card.kind] ?? "bg-zinc-400 ring-zinc-200"} hover:scale-150`}
            style={{ left: `${marker.pct}%` }}
          />
        ))}
        <div
          className="absolute top-0 h-full w-0.5 bg-[var(--text-primary)]/40"
          style={{ left: "100%" }}
        />
      </div>

      <div className="relative h-4 w-full text-[10px] text-[var(--text-muted)]">
        {ticks.map((tick) => (
          <span
            key={tick.pct}
            className="absolute -translate-x-1/2 tabular-nums"
            style={{ left: `${Math.min(96, Math.max(2, tick.pct))}%` }}
          >
            {tick.label}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[var(--text-muted)]">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> decision
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-amber-500" /> risk
        </span>
        <span>· markers = open items by date · click to open · vertical line = today</span>
      </div>

      {hover && (
        <div className="rounded-md border border-[var(--border-default)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          <span className="font-medium uppercase">{hover.card.kind}</span> · {hover.card.summary}
        </div>
      )}
    </div>
  );
}
