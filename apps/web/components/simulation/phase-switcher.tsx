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
  const { currentProjectId, currentUserId, currentDay } = useImpersonationStore();
  const queryClient = useQueryClient();
  // Local optimistic value: the dropdown reflects what the user just picked
  // immediately, even while the backend mutation + digest regen are in
  // flight (~3-10s). Cleared on settle so we fall back to the canonical
  // value from the project query.
  const [optimisticPhase, setOptimisticPhase] = useState<string | null>(null);

  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  const setPhase = useMutation({
    mutationFn: async (phase: string) => {
      await api.changePhase(currentProjectId!, phase);
      if (currentUserId) {
        await api.regenerateDigest(currentUserId, currentProjectId!, currentDay);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project"] });
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
    onSettled: () => {
      setOptimisticPhase(null);
    },
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
      {setPhase.isPending && <Spinner size="xs" label="Re-ranking…" />}
      {setPhase.isError && <span className="text-xs text-red-700">phase change failed</span>}
    </div>
  );
}
