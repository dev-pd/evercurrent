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
        <h3 className="text-xs font-semibold tracking-wider text-[var(--text-secondary)] uppercase">
          Potential conflicts
        </h3>
        <div className="flex gap-1">
          {affectedSubsystems.map((subsystem) => (
            <span
              key={subsystem}
              className="rounded-md border border-[var(--border-default)] bg-white px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-[var(--text-secondary)] uppercase"
            >
              {subsystem}
            </span>
          ))}
        </div>
      </div>
      <ul className="mt-3 flex flex-col gap-2">
        {conflicts.map((conflict, idx) => (
          <li
            key={idx}
            className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 ${SEVERITY_CLASSES[conflict.severity]}`}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{conflict.title}</span>
                <span className="shrink-0 rounded border border-current/20 bg-white/50 px-1.5 py-0.5 font-mono text-[10px] tracking-wide uppercase opacity-70">
                  {conflict.subsystem}
                </span>
              </div>
              <p className="mt-1 text-xs opacity-80">{conflict.detail}</p>
              {conflict.impact && (
                <p className="mt-1.5 text-xs">
                  <span className="font-semibold tracking-wide uppercase opacity-60">Impact </span>
                  <span className="opacity-90">{conflict.impact}</span>
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
