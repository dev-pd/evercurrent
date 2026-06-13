"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Loader2 } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import type { MemberSummary } from "@/lib/types";

const ROLES = [
  { value: "", label: "— role —" },
  { value: "mech", label: "Mechanical" },
  { value: "ee", label: "Electrical" },
  { value: "fw", label: "Firmware" },
  { value: "qa", label: "QA" },
  { value: "supply", label: "Supply chain" },
  { value: "em", label: "Eng manager" },
];

export function TeamCard({ members }: { members: MemberSummary[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Team</h2>
      <p className="text-xs text-[var(--text-muted)]">
        Assign each member their engineering role and the subsystems they own — this is what
        personalizes their digest.
      </p>
      <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
        {members.length === 0 ? (
          <div className="p-4 text-sm text-[var(--text-muted)]">
            No members yet. They appear here after their first login.
          </div>
        ) : (
          members.map((m, i) => <MemberRow key={m.id} member={m} divider={i > 0} />)
        )}
      </div>
    </section>
  );
}

function MemberRow({ member, divider }: { member: MemberSummary; divider: boolean }) {
  const router = useRouter();
  const [role, setRole] = useState(member.eng_role ?? "");
  const [subs, setSubs] = useState(member.owned_subsystems.join(", "));
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");

  const dirty = role !== (member.eng_role ?? "") || subs !== member.owned_subsystems.join(", ");

  async function save() {
    setState("saving");
    try {
      await apiBrowser().updateMember(member.id, {
        eng_role: role || null,
        owned_subsystems: subs
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setState("saved");
      router.refresh();
    } catch {
      setState("idle");
    }
  }

  return (
    <div
      className={`flex flex-wrap items-center gap-3 p-4 ${
        divider ? "border-t border-[var(--border-default)]" : ""
      }`}
    >
      <span className="w-32 shrink-0 truncate text-sm font-medium text-[var(--text-primary)]">
        {member.display_name}
      </span>
      <select
        value={role}
        onChange={(e) => {
          setRole(e.target.value);
          setState("idle");
        }}
        className="rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm"
      >
        {ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <input
        value={subs}
        onChange={(e) => {
          setSubs(e.target.value);
          setState("idle");
        }}
        placeholder="subsystems, comma-separated"
        className="min-w-0 flex-1 rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm"
      />
      <button
        type="button"
        onClick={save}
        disabled={!dirty || state === "saving"}
        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] px-3 py-1 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
      >
        {state === "saving" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {state === "saved" && <Check className="h-3.5 w-3.5 text-emerald-600" />}
        {state === "saved" ? "Saved" : "Save"}
      </button>
    </div>
  );
}
