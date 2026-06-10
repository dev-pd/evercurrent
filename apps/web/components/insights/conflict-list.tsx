import { AlertTriangle } from "lucide-react";
import type { InsightConflict } from "@/lib/types";

const SEVERITY_CLASSES: Record<InsightConflict["severity"], string> = {
  info: "border-zinc-200 bg-zinc-50 text-zinc-700",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  critical: "border-red-200 bg-red-50 text-red-800",
};

interface ConflictListProps {
  conflicts: InsightConflict[];
  affectedSubsystems: string[];
}

export function ConflictList({ conflicts, affectedSubsystems }: ConflictListProps) {
  return (
    <section className="border-t border-[var(--color-accent-100)] bg-white/60 px-5 py-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Potential conflicts
        </h3>
        <div className="flex gap-1">
          {affectedSubsystems.map((s) => (
            <span
              key={s}
              className="rounded-md border border-[var(--border-default)] bg-white px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--text-secondary)]"
            >
              {s}
            </span>
          ))}
        </div>
      </div>
      <ul className="mt-3 flex flex-col gap-2">
        {conflicts.map((c, idx) => (
          <li
            key={idx}
            className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 ${SEVERITY_CLASSES[c.severity]}`}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-medium">{c.title}</span>
                <span className="shrink-0 font-mono text-xs tabular-nums">{c.impact}</span>
              </div>
              <p className="mt-0.5 text-xs opacity-80">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
