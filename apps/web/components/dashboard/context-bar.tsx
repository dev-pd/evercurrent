import { CircuitBoard } from "lucide-react";
import type { MemberSummary } from "@/lib/types";
import { KpiTile } from "@/components/ui/kpi-tile";
import { RegenerateButton } from "./regenerate-button";
import { LiveUpdatesBadge } from "./live-updates-badge";

const ROLE_LABEL: Record<string, string> = {
  mech: "Mechanical",
  ee: "Electrical",
  fw: "Firmware",
  sw: "Software",
  qa: "QA",
  supply: "Supply Chain",
  em: "Eng Manager",
  pm: "Product",
};

function roleLabel(role: string | null): string {
  if (!role) return "Member";
  return ROLE_LABEL[role] ?? role;
}

export interface Kpi {
  label: string;
  value: number | string;
  hint?: string;
}

interface ContextBarProps {
  currentMember: MemberSummary | null;
  phase: string;
  dayIndex: number;
  summary: string;
  projectId: string | null;
  generatedAt: string | null;
  kpis: Kpi[];
}

export function ContextBar({
  currentMember,
  phase,
  dayIndex,
  summary,
  projectId,
  generatedAt,
  kpis,
}: ContextBarProps) {
  return (
    <div className="glass glass-sheen flex flex-col gap-3 rounded-xl border border-[var(--glass-border)] px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
            <CircuitBoard className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold text-[var(--text-primary)]">
              {currentMember?.display_name ?? "Your digest"}
              <span className="ml-2 font-normal text-[var(--text-muted)]">
                · {roleLabel(currentMember?.eng_role ?? null)}
              </span>
            </span>
            <span className="text-xs text-[var(--text-muted)]">
              Phase {phase} · Day {dayIndex}
              {currentMember && currentMember.owned_subsystems.length > 0 && (
                <> · owns {currentMember.owned_subsystems.join(", ")}</>
              )}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <LiveUpdatesBadge projectId={projectId} generatedAt={generatedAt} />
          <RegenerateButton />
        </div>
      </div>

      <p className="text-sm text-[var(--text-secondary)]">{summary}</p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {kpis.map((k) => (
          <KpiTile key={k.label} label={k.label} value={k.value} hint={k.hint} />
        ))}
      </div>
    </div>
  );
}
