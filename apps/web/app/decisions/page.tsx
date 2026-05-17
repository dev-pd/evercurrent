"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  proposed: "bg-amber-100 text-amber-800",
  decided: "bg-emerald-100 text-emerald-800",
  implemented: "bg-blue-100 text-blue-800",
  reverted: "bg-zinc-200 text-zinc-700",
};

function tokenise(values: string[]): string[] {
  return values
    .flatMap((v) => v.split(/[_\s,-]+/))
    .map((t) => t.trim().toLowerCase())
    .filter((t) => t.length > 2);
}

function affects(decision: Decision, userTokens: string[]): boolean {
  if (userTokens.length === 0) return true;
  const decisionTokens = tokenise(decision.affected_subsystems);
  return decisionTokens.some((dt) => userTokens.some((ut) => dt.includes(ut) || ut.includes(dt)));
}

export default function DecisionsPage() {
  const { currentProjectId, currentUserId } = useImpersonationStore();
  const [showAll, setShowAll] = useState(false);

  const decisions = useQuery({
    queryKey: ["decisions", currentProjectId],
    queryFn: () => api.listDecisions(currentProjectId!),
    enabled: Boolean(currentProjectId),
    retry: false,
  });

  const users = useQuery({
    queryKey: ["users", currentProjectId],
    queryFn: () => api.listUsers(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  const currentUser = users.data?.find((u) => u.id === currentUserId);
  const userTokens = useMemo(
    () =>
      currentUser ? tokenise([...currentUser.owned_subsystems, ...currentUser.owned_parts]) : [],
    [currentUser],
  );

  const visible = useMemo(() => {
    if (!decisions.data) return [];
    if (showAll || !currentUser) return decisions.data;
    return decisions.data.filter((d) => affects(d, userTokens));
  }, [decisions.data, showAll, currentUser, userTokens]);

  return (
    <AppShell>
      <div className="p-6">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold">Decisions</h1>
            <p className="text-sm text-zinc-500">
              Structured decisions extracted from team conversations.
              {currentUser && !showAll
                ? ` Filtered to subsystems owned by ${currentUser.display_name}.`
                : " Showing every decision in the project."}
            </p>
          </div>
          {currentUser && (
            <Button variant="outline" size="sm" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Filter to me" : "Show all"}
            </Button>
          )}
        </div>
        {decisions.isLoading && <Spinner label="Loading decisions…" />}
        {decisions.isError && (
          <p className="text-sm text-zinc-500">
            Decisions endpoint unreachable — run the pipeline to extract some.
          </p>
        )}
        {!decisions.isLoading && visible.length === 0 && (
          <p className="text-sm text-zinc-500">
            {decisions.data?.length
              ? 'No decisions affect the impersonated user. Switch to a different user or click "Show all".'
              : "No decisions extracted yet."}
          </p>
        )}
        <div className="flex flex-col gap-3">
          {visible.map((d) => (
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
