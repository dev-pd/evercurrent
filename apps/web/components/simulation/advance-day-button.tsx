"use client";

import { Button } from "@/components/ui/button";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

interface SimulationStatus {
  current_day: number;
}

interface JobResponse {
  job_id: string;
  day: number;
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function fetchStatus(projectId: string): Promise<SimulationStatus> {
  const r = await fetch(`${BASE}/simulation/status?project_id=${projectId}`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return (await r.json()) as SimulationStatus;
}

async function postAdvance(projectId: string): Promise<JobResponse> {
  const r = await fetch(`${BASE}/simulation/advance-day?project_id=${projectId}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(`advance ${r.status}`);
  return (await r.json()) as JobResponse;
}

export function AdvanceDayButton() {
  const { currentProjectId, setCurrentDay } = useImpersonationStore();
  const queryClient = useQueryClient();
  const [pendingTargetDay, setPendingTargetDay] = useState<number | null>(null);

  const status = useQuery({
    queryKey: ["simulation-status", currentProjectId],
    queryFn: () => fetchStatus(currentProjectId!),
    enabled: Boolean(currentProjectId),
    refetchInterval: pendingTargetDay !== null ? 2000 : false,
  });

  const advance = useMutation({
    mutationFn: () => postAdvance(currentProjectId!),
    onSuccess: (data) => setPendingTargetDay(data.day),
  });

  useEffect(() => {
    if (pendingTargetDay === null) return;
    if (!status.data || status.data.current_day < pendingTargetDay) return;
    const queueMicrotask =
      typeof globalThis.queueMicrotask === "function"
        ? globalThis.queueMicrotask
        : (cb: () => void) => Promise.resolve().then(cb);
    queueMicrotask(() => {
      setCurrentDay(pendingTargetDay);
      setPendingTargetDay(null);
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
      void queryClient.invalidateQueries({ queryKey: ["project"] });
      void queryClient.invalidateQueries({ queryKey: ["decisions"] });
    });
  }, [pendingTargetDay, status.data, setCurrentDay, queryClient]);

  if (!currentProjectId) return null;

  return (
    <Button
      onClick={() => advance.mutate()}
      disabled={advance.isPending || pendingTargetDay !== null}
      size="sm"
    >
      {pendingTargetDay !== null
        ? `Advancing to day ${pendingTargetDay}…`
        : advance.isPending
          ? "Enqueuing…"
          : "Advance day"}
    </Button>
  );
}
