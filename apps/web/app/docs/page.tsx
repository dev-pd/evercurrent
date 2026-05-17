"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

const KIND_LABEL: Record<string, string> = {
  prd: "PRD",
  bom: "BOM",
  eco_log: "ECO Log",
  test_report_thermal: "Thermal Test Report",
  test_report_drop: "Drop Test Report",
  other: "Other",
};

export default function DocsPage() {
  const { currentProjectId } = useImpersonationStore();
  const [filterCurrentPhaseOnly, setFilterCurrentPhaseOnly] = useState(true);

  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  const phase = filterCurrentPhaseOnly ? (project.data?.current_phase ?? undefined) : undefined;

  const docs = useQuery({
    queryKey: ["documents", currentProjectId, phase],
    queryFn: () => api.listDocuments(currentProjectId!, phase),
    enabled: Boolean(currentProjectId),
  });

  return (
    <AppShell>
      <div className="p-6">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold">Project documents</h1>
            <p className="text-sm text-zinc-500">
              Each doc is tagged with the project phases it is authoritative for. RAG retrieval
              filters by the current phase by default — so the agent doesn&apos;t cite test reports
              that haven&apos;t happened yet.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-zinc-600">
            <input
              type="checkbox"
              checked={filterCurrentPhaseOnly}
              onChange={(e) => setFilterCurrentPhaseOnly(e.target.checked)}
            />
            Filter to current phase ({project.data?.current_phase ?? "—"})
          </label>
        </div>
        {docs.isLoading && <Spinner label="Loading documents…" />}
        {docs.data?.length === 0 && <p className="text-sm text-zinc-500">No documents seeded.</p>}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {docs.data?.map((d) => (
            <Card key={d.id}>
              <CardHeader>
                <CardTitle className="text-base">{d.title}</CardTitle>
                <p className="text-xs text-zinc-500">
                  {KIND_LABEL[d.kind] ?? d.kind} · {d.chars.toLocaleString()} chars
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {d.phases.length === 0 ? (
                    <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 uppercase">
                      all phases
                    </span>
                  ) : (
                    d.phases.map((p) => {
                      const active = p === project.data?.current_phase;
                      return (
                        <span
                          key={p}
                          className={`rounded px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${
                            active ? "bg-emerald-100 text-emerald-800" : "bg-zinc-100 text-zinc-600"
                          }`}
                        >
                          {p}
                        </span>
                      );
                    })
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="line-clamp-4 text-xs text-zinc-700">{d.body_excerpt}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
