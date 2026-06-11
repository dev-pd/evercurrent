"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { ChevronDown, CircuitBoard } from "lucide-react";
import type { MemberSummary } from "@/lib/types";
import { RegenerateButton } from "./regenerate-button";

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

interface ContextBarProps {
  members: MemberSummary[];
  currentMember: MemberSummary | null;
  phase: string;
  dayIndex: number;
  summary: string;
}

export function ContextBar({
  members,
  currentMember,
  phase,
  dayIndex,
  summary,
}: ContextBarProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function onSwitch(id: string) {
    startTransition(() => {
      router.push(`/dashboard?as=${encodeURIComponent(id)}`);
    });
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-[var(--border-default)] bg-white px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
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
          <label className="relative flex items-center">
            <span className="pointer-events-none absolute left-3 text-xs text-[var(--text-muted)]">
              View as
            </span>
            <select
              aria-label="View as member"
              value={currentMember?.id ?? ""}
              disabled={isPending}
              onChange={(e) => onSwitch(e.target.value)}
              className="appearance-none rounded-md border border-[var(--border-default)] bg-[var(--surface-muted)] py-1.5 pl-[4.5rem] pr-8 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--border-strong)] disabled:opacity-60"
            >
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name} — {roleLabel(m.eng_role)}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[var(--text-muted)]"
              aria-hidden="true"
            />
          </label>
          <RegenerateButton />
        </div>
      </div>

      <p className="text-sm text-[var(--text-secondary)]">{summary}</p>
    </div>
  );
}
