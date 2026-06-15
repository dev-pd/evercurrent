import { roleLabel } from "@/lib/roles";
import { messages } from "@/lib/messages";
import type { MemberSummary } from "@/lib/types";

const t = messages.team;

export function TeamCard({ members }: { members: MemberSummary[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t.heading}</h2>
      <p className="text-xs text-[var(--text-muted)]">{t.hint}</p>
      <div className="glass-strong overflow-hidden rounded-lg border border-[var(--glass-border)]">
        {members.length === 0 ? (
          <div className="p-4 text-sm text-[var(--text-muted)]">{t.empty}</div>
        ) : (
          members.map((m, i) => <MemberRow key={m.id} member={m} divider={i > 0} />)
        )}
      </div>
    </section>
  );
}

function MemberRow({ member, divider }: { member: MemberSummary; divider: boolean }) {
  return (
    <div
      className={`flex flex-wrap items-center gap-3 p-4 ${
        divider ? "border-t border-[var(--border-default)]" : ""
      }`}
    >
      <span className="w-36 shrink-0 truncate text-sm font-medium text-[var(--text-primary)]">
        {member.display_name}
      </span>
      <span className="shrink-0 rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
        {roleLabel(member.eng_role)}
      </span>
      <div className="flex min-w-0 flex-1 flex-wrap gap-1">
        {member.owned_subsystems.length === 0 ? (
          <span className="text-xs text-[var(--text-muted)]">—</span>
        ) : (
          member.owned_subsystems.map((s) => (
            <span
              key={s}
              className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[11px] text-[var(--text-secondary)]"
            >
              {s}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
