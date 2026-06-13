import { Target, TrendingDown, TrendingUp } from "lucide-react";
import type { FocusTopic } from "@/lib/types";

const SOURCE_META: Record<string, { label: string; cls: string }> = {
  role: { label: "your role", cls: "bg-indigo-100 text-indigo-700" },
  phase: { label: "this phase", cls: "bg-amber-100 text-amber-700" },
  learned: { label: "your activity", cls: "bg-emerald-100 text-emerald-700" },
};

export function FocusPanel({ focus }: { focus: FocusTopic[] }) {
  if (focus.length === 0) return null;
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-white px-5 py-3">
      <div className="mb-2 flex items-center gap-2">
        <Target className="h-3.5 w-3.5 text-[var(--color-accent-600)]" aria-hidden="true" />
        <h2 className="text-xs font-semibold tracking-wider text-[var(--text-secondary)] uppercase">
          What you&apos;re tracking now
        </h2>
        <span className="text-[11px] text-[var(--text-muted)]">
          built from your role, the project phase, and what you engage with
        </span>
      </div>
      <div className="divide-y divide-[var(--border-default)]">
        {focus.map((item) => (
          <div key={item.topic} className="flex items-center gap-3 py-1.5">
            <div className="flex w-36 shrink-0 items-center gap-1.5">
              <span className="truncate text-xs font-medium text-[var(--text-primary)]">
                {item.label}
              </span>
              {item.trend === "up" && (
                <TrendingUp className="h-3 w-3 text-emerald-600" aria-label="rising" />
              )}
              {item.trend === "down" && (
                <TrendingDown className="h-3 w-3 text-zinc-400" aria-label="fading" />
              )}
            </div>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]">
              <div
                className="h-full rounded-full bg-[var(--color-accent-500)]"
                style={{ width: `${Math.round(item.weight * 100)}%` }}
              />
            </div>
            <div className="flex w-44 shrink-0 flex-wrap justify-end gap-1">
              {item.sources.map((s) => (
                <span
                  key={s}
                  className={`rounded px-1.5 py-0.5 text-[9px] font-medium ${SOURCE_META[s]?.cls ?? ""}`}
                >
                  {SOURCE_META[s]?.label ?? s}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
