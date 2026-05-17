"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQuery } from "@tanstack/react-query";

const STATUS_COLOR: Record<string, string> = {
  proposed: "bg-amber-100 text-amber-800",
  decided: "bg-emerald-100 text-emerald-800",
  implemented: "bg-blue-100 text-blue-800",
  reverted: "bg-zinc-200 text-zinc-700",
};

export default function DecisionsPage() {
  const { currentProjectId } = useImpersonationStore();
  const decisions = useQuery({
    queryKey: ["decisions", currentProjectId],
    queryFn: () => api.listDecisions(currentProjectId!),
    enabled: Boolean(currentProjectId),
    retry: false,
  });

  return (
    <AppShell>
      <div className="p-6">
        <h1 className="mb-1 text-xl font-semibold">Decisions</h1>
        <p className="mb-6 text-sm text-zinc-500">
          Structured decisions extracted from team conversations. Day-advance triggers extraction;
          refresh after a few seconds.
        </p>
        {decisions.isError && (
          <p className="text-sm text-zinc-500">
            No decisions endpoint yet; run a day advance or wait for extraction.
          </p>
        )}
        {decisions.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
        {decisions.data?.length === 0 && (
          <p className="text-sm text-zinc-500">No decisions extracted yet.</p>
        )}
        <div className="flex flex-col gap-3">
          {decisions.data?.map((d) => (
            <Card key={d.id}>
              <CardHeader className="flex flex-row items-start justify-between">
                <div>
                  <CardTitle className="text-base">{d.summary}</CardTitle>
                  <p className="text-xs text-zinc-500">
                    {d.decided_by} · {new Date(d.decided_at).toLocaleString()}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-1 text-xs ${STATUS_COLOR[d.status] ?? "bg-zinc-100 text-zinc-700"}`}
                >
                  {d.status}
                </span>
              </CardHeader>
              <CardContent className="text-sm">
                {d.rationale && <p className="mb-2 text-zinc-700">{d.rationale}</p>}
                {d.affected_subsystems.length > 0 && (
                  <p className="text-xs text-zinc-500">
                    Affected: {d.affected_subsystems.join(", ")}
                  </p>
                )}
                <p className="text-xs text-zinc-400">
                  confidence {(d.confidence * 100).toFixed(0)}% · {d.source_message_ids.length}{" "}
                  sources
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
