import type { SpecSnapshot } from "@/lib/types";

interface SpecDiffProps {
  label: string;
  specs: SpecSnapshot[];
  tone: "before" | "after";
}

export function SpecDiff({ label, specs, tone }: SpecDiffProps) {
  const accent =
    tone === "after"
      ? "border-emerald-200 bg-emerald-50/60"
      : "border-zinc-200 bg-white";
  return (
    <div className={`rounded-lg border p-3 ${accent}`}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </div>
      <dl className="mt-2 flex flex-col gap-1.5">
        {specs.map((s) => (
          <div key={s.label} className="flex items-baseline justify-between gap-3">
            <dt className="text-xs text-[var(--text-secondary)]">{s.label}</dt>
            <dd className="font-mono text-sm tabular-nums text-[var(--text-primary)]">
              {s.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
