import type { ReactNode } from "react";

interface KpiTileProps {
  label: string;
  value: ReactNode;
  hint?: string;
}

/** Compact metric tile. Reused in the digest context bar and elsewhere. */
export function KpiTile({ label, value, hint }: KpiTileProps) {
  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface-muted)] px-3 py-2.5">
      <div className="font-mono text-lg font-semibold leading-none tabular-nums text-[var(--text-primary)]">
        {value}
      </div>
      <div className="mt-1 text-[11px] text-[var(--text-muted)]">{label}</div>
      {hint && <div className="text-[10px] text-[var(--text-muted)]">{hint}</div>}
    </div>
  );
}
