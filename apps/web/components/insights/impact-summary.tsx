interface ImpactSummaryProps {
  impact: Record<string, string>;
}

function ImpactStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-default)] bg-white p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm tabular-nums text-[var(--text-primary)]">
        {value}
      </div>
    </div>
  );
}

export function ImpactSummary({ impact }: ImpactSummaryProps) {
  return (
    <section className="border-t border-[var(--color-accent-100)] bg-white/60 px-5 py-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        Impact summary
      </h3>
      <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
        <ImpactStat label="Cost" value={impact.cost ?? "—"} />
        <ImpactStat label="Schedule" value={impact.schedule ?? "—"} />
        <ImpactStat label="Revenue at risk" value={impact.revenue_at_risk ?? "—"} />
      </div>
    </section>
  );
}
