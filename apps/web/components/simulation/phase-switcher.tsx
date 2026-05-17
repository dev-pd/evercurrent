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

const PHASES = ["concept", "design", "EVT", "DVT", "PVT", "MP"];

export function PhaseSwitcher() {
  const { currentProjectId, currentUserId, currentDay } = useImpersonationStore();
  const queryClient = useQueryClient();
  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  const setPhase = useMutation({
    mutationFn: async (phase: string) => {
      await api.changePhase(currentProjectId!, phase);
      // Regenerate the current user's digest synchronously so the reshuffle
      // is visible right away. Other users pick up the new phase next refetch.
      if (currentUserId) {
        await api.regenerateDigest(currentUserId, currentProjectId!, currentDay);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project"] });
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
  });

  if (!project.data) {
    return <Spinner size="xs" label="Loading phase…" />;
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">Phase</span>
      <Select
        value={project.data.current_phase}
        onValueChange={(v) => setPhase.mutate(v)}
        disabled={setPhase.isPending}
      >
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
    </div>
  );
}
