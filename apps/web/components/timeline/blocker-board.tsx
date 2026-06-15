import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import type { CardListItem } from "@/lib/types";

function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
}

export function BlockerBoard({ cards, limit = 8 }: { cards: CardListItem[]; limit?: number }) {
  const blockers = cards
    .filter((c) => c.kind === "risk" && c.status === "open")
    .sort((a, b) => (b.occurred_at ?? "").localeCompare(a.occurred_at ?? ""))
    .slice(0, limit);

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-[var(--border-default)] bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <AlertTriangle className="h-4 w-4 text-amber-500" /> Active blockers
        </h3>
        <span className="font-mono text-xs text-[var(--text-muted)] tabular-nums">
          {blockers.length}
        </span>
      </div>

      {blockers.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No open blockers. Clear runway.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {blockers.map((b) => (
            <li key={b.id}>
              <Link
                href={`/decisions/${b.id}`}
                className="group flex items-start gap-3 rounded-md border border-[var(--border-default)] p-3 hover:bg-[var(--surface-muted)]"
              >
                <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--color-accent-700)]">
                    {b.summary}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                    {b.affected_subsystems.slice(0, 4).map((s) => (
                      <span
                        key={s}
                        className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[var(--text-secondary)]"
                      >
                        {s}
                      </span>
                    ))}
                    <span className="ml-auto tabular-nums">{ago(b.occurred_at)}</span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
