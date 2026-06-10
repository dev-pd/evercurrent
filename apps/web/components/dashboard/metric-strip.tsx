import { AlertTriangle, FileCheck, Inbox, ScanSearch } from "lucide-react";
import type { ComponentType, SVGProps } from "react";

interface Metric {
  label: string;
  value: number | string;
  hint: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  accent?: "neutral" | "warning" | "ok";
}

interface MetricStripProps {
  signals: number;
  decisions: number;
  risks: number;
  docs: number;
}

export function MetricStrip({ signals, decisions, risks, docs }: MetricStripProps) {
  const metrics: Metric[] = [
    {
      label: "Signals today",
      value: signals,
      hint: "Slack messages routed",
      icon: Inbox,
    },
    {
      label: "Decisions",
      value: decisions,
      hint: "Extracted this week",
      icon: FileCheck,
      accent: "ok",
    },
    {
      label: "Open risks",
      value: risks,
      hint: "Needs your attention",
      icon: AlertTriangle,
      accent: risks > 0 ? "warning" : "neutral",
    },
    {
      label: "Docs indexed",
      value: docs,
      hint: "PDFs in knowledge graph",
      icon: ScanSearch,
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {metrics.map((m) => (
        <MetricCard key={m.label} metric={m} />
      ))}
    </div>
  );
}

function MetricCard({ metric }: { metric: Metric }) {
  const Icon = metric.icon;
  const accentRing =
    metric.accent === "warning"
      ? "border-amber-200 bg-amber-50"
      : metric.accent === "ok"
        ? "border-emerald-200 bg-emerald-50"
        : "border-[var(--border-default)] bg-white";
  return (
    <div className={`flex flex-col gap-1 rounded-lg border p-3 ${accentRing}`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {metric.label}
        </span>
        <Icon className="h-3.5 w-3.5 text-[var(--text-muted)]" aria-hidden="true" />
      </div>
      <div className="font-mono text-2xl font-semibold leading-none tabular-nums text-[var(--text-primary)]">
        {metric.value}
      </div>
      <div className="text-[11px] text-[var(--text-muted)]">{metric.hint}</div>
    </div>
  );
}
