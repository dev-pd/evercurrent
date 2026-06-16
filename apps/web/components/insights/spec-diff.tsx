import type { SpecSnapshot } from "@/lib/types";

interface SpecDiffProps {
  label: string;
  specs: SpecSnapshot[];
  tone: "before" | "after";
}

export function SpecDiff({ label, specs, tone }: SpecDiffProps) {
  const accent =
    tone === "after" ? "border-emerald-200 bg-emerald-50/60" : "border-zinc-200 bg-white";
  return (
    <div className={`rounded-lg border p-3 ${accent}`}>
      <div className="text-[10px] font-semibold tracking-wider text-[var(--text-muted)] uppercase">
        {label}
      </div>
      <dl className="mt-2 flex flex-col gap-2">
        {specs.map((spec) => (
          <div key={spec.label} className="min-w-0">
            <dt className="text-[10px] tracking-wide text-[var(--text-muted)] uppercase">
              {spec.label}
            </dt>
            <dd className="mt-0.5 font-mono text-sm break-words text-[var(--text-primary)]">
              {spec.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
