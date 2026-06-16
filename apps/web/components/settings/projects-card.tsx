"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FolderPlus, Loader2 } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { messages } from "@/lib/messages";
import type { Project } from "@/lib/types";

const copy = messages.projects;

const PHASES = [
  { value: "evt", label: "EVT" },
  { value: "dvt", label: "DVT" },
  { value: "pvt", label: "PVT" },
  { value: "fcs", label: "FCS" },
] as const;

const DEFAULT_CONCERNS: Record<string, string[]> = {
  evt: ["bring-up", "schematic", "first-light", "DFM"],
  dvt: ["reliability", "test", "thermal", "margin"],
  pvt: ["yield", "process", "build-readiness", "tooling"],
  fcs: ["ramp", "field", "RMA", "sustaining"],
};

export function ProjectsCard({ projects }: { projects: Project[] }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<string>("dvt");
  const [startDate, setStartDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!name.trim() || !startDate) {
      setError(copy.validationRequired);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiBrowser().createProject({
        name: name.trim(),
        current_phase: phase,
        start_date: startDate,
        phase_concerns: DEFAULT_CONCERNS,
      });
      setName("");
      setStartDate("");
      router.refresh();
    } catch {
      setError(copy.createFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">{copy.heading}</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
        {projects.length === 0 ? (
          <p className="p-4 text-xs text-[var(--text-muted)]">{copy.empty}</p>
        ) : (
          projects.map((project, i) => (
            <div
              key={project.id}
              className={`flex items-center justify-between gap-3 p-4 ${
                i > 0 ? "border-t border-[var(--border-default)]" : ""
              }`}
            >
              <span className="text-sm font-medium text-[var(--text-primary)]">{project.name}</span>
              <span className="inline-flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 font-medium uppercase">
                  {project.current_phase}
                </span>
                {copy.dayPrefix} {project.current_day}
              </span>
            </div>
          ))
        )}
        {projects.length === 0 && (
          <div className="flex flex-wrap items-end gap-2 border-t border-[var(--border-default)] bg-[var(--surface-muted)] p-4">
            <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
              {copy.nameLabel}
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={copy.namePlaceholder}
                className="w-44 rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm text-[var(--text-primary)]"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
              {copy.phaseLabel}
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm text-[var(--text-primary)]"
              >
                {PHASES.map((ph) => (
                  <option key={ph.value} value={ph.value}>
                    {ph.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
              {copy.startDateLabel}
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-md border border-[var(--border-default)] bg-white px-2 py-1 text-sm text-[var(--text-primary)]"
              />
            </label>
            <button
              type="button"
              onClick={create}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--color-accent-700)] disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderPlus className="h-4 w-4" />
              )}
              {copy.create}
            </button>
          </div>
        )}
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </section>
  );
}
