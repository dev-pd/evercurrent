import { messages } from "@/lib/messages";

const copy = messages.insights;

interface ImpactSummaryProps {
  impact: Record<string, string>;
}

function ImpactStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-default)] bg-white p-2.5">
      <div className="text-[10px] tracking-wider text-[var(--text-muted)] uppercase">{label}</div>
      <div className="mt-1 text-xs leading-snug break-words text-[var(--text-primary)]">
        {value}
      </div>
    </div>
  );
}

export function ImpactSummary({ impact }: ImpactSummaryProps) {
  const candidates: { label: string; value: string | undefined }[] = [
    { label: copy.impactCost, value: impact.cost },
    { label: copy.impactSchedule, value: impact.schedule },
    { label: copy.impactRevenueAtRisk, value: impact.revenue_at_risk },
  ];
  const stats = candidates.filter(
    (stat): stat is { label: string; value: string } => Boolean(stat.value),
  );

  if (stats.length === 0) return null;

  return (
    <section className="border-t border-[var(--color-accent-100)] bg-white/60 px-5 py-4">
      <h3 className="text-xs font-semibold tracking-wider text-[var(--text-secondary)] uppercase">
        {copy.impactSummaryHeading}
      </h3>
      <div className="mt-2 grid grid-cols-1 gap-3 text-xs sm:grid-cols-3">
        {stats.map((stat) => (
          <ImpactStat key={stat.label} label={stat.label} value={stat.value} />
        ))}
      </div>
    </section>
  );
}
