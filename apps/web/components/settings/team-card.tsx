"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Loader2, Plus } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { ENG_ROLES } from "@/lib/roles";
import { messages } from "@/lib/messages";
import type { MemberSummary } from "@/lib/types";

const t = messages.team;

function parseSubs(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function TeamCard({ members }: { members: MemberSummary[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t.heading}</h2>
      <p className="text-xs text-[var(--text-muted)]">{t.hint}</p>
      <div className="glass-strong overflow-hidden rounded-lg border border-[var(--glass-border)]">
        <AddMemberForm />
        {members.length === 0 ? (
          <div className="border-t border-[var(--border-default)] p-4 text-sm text-[var(--text-muted)]">
            {t.empty}
          </div>
        ) : (
          members.map((m) => <MemberRow key={m.id} member={m} divider />)
        )}
      </div>
    </section>
  );
}

function AddMemberForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [subs, setSubs] = useState("");
  const [saving, setSaving] = useState(false);

  async function add() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiBrowser().createMember({
        display_name: name.trim(),
        eng_role: role || null,
        owned_subsystems: parseSubs(subs),
      });
      setName("");
      setRole("");
      setSubs("");
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 bg-[var(--surface-muted)]/40 p-3">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t.namePlaceholder}
        className="w-44 rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm"
      />
      <select
        value={role}
        onChange={(e) => setRole(e.target.value)}
        className="rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm"
      >
        <option value="">{t.rolePlaceholder}</option>
        {ENG_ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <input
        value={subs}
        onChange={(e) => setSubs(e.target.value)}
        placeholder={t.subsystemsPlaceholder}
        className="min-w-0 flex-1 rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm"
      />
      <button
        type="button"
        onClick={add}
        disabled={!name.trim() || saving}
        className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-600)] px-3 py-1 text-sm font-medium text-white hover:bg-[var(--color-accent-700)] disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Plus className="h-3.5 w-3.5" />
        )}
        {t.add}
      </button>
    </div>
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
        <option value="">{t.rolePlaceholder}</option>
        {ENG_ROLES.map((r) => (
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
        placeholder={t.subsystemsPlaceholder}
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
        {state === "saved" ? t.saved : t.save}
      </button>
    </div>
  );
}
