"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

const PHASES = ["concept", "design", "EVT", "DVT", "PVT", "MP"];

export function PhaseSwitcher() {
  const { currentProjectId } = useImpersonationStore();
  const queryClient = useQueryClient();
  const [optimisticPhase, setOptimisticPhase] = useState<string | null>(null);

  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  // Phase change is a metadata-only POST. Every (user, day, phase) digest
  // is precomputed at seed, so the dashboard refetches the matching
  // precomputed row — no LLM call in this hot path.
  const setPhase = useMutation({
    mutationFn: (phase: string) => api.changePhase(currentProjectId!, phase),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project"] });
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
    onSettled: () => setOptimisticPhase(null),
  });

  if (!project.data) {
    return <Spinner size="xs" label="Loading phase…" />;
  }

  const selected = optimisticPhase ?? project.data.current_phase;

  const handleChange = (next: string) => {
    if (next === selected) return;
    setOptimisticPhase(next);
    setPhase.mutate(next);
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">Phase</span>
      <Select value={selected} onValueChange={handleChange}>
        <SelectTrigger className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PHASES.map((p) => (
            <SelectItem key={p} value={p}>
              {p}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {setPhase.isPending && <Spinner size="xs" />}
      {setPhase.isError && <span className="text-xs text-red-700">phase change failed</span>}
    </div>
  );
}
