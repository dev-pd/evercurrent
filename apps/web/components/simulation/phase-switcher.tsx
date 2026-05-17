"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const PHASES = ["concept", "design", "EVT", "DVT", "PVT", "MP"];

export function PhaseSwitcher() {
  const { currentProjectId } = useImpersonationStore();
  const queryClient = useQueryClient();
  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });

  const setPhase = useMutation({
    mutationFn: (phase: string) => api.changePhase(currentProjectId!, phase),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project"] });
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
  });

  if (!project.data) return null;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">Phase</span>
      <Select value={project.data.current_phase} onValueChange={(v) => setPhase.mutate(v)}>
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
    </div>
  );
}
