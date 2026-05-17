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
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

export function ImpersonationDropdown() {
  const { currentProjectId, currentUserId, setCurrentProjectId, setCurrentUserId } =
    useImpersonationStore();

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const projectId = currentProjectId ?? projects.data?.[0]?.id ?? null;

  useEffect(() => {
    if (!currentProjectId && projects.data?.[0]?.id) {
      setCurrentProjectId(projects.data[0].id);
    }
  }, [currentProjectId, projects.data, setCurrentProjectId]);

  const users = useQuery({
    queryKey: ["users", projectId],
    queryFn: () => api.listUsers(projectId!),
    enabled: Boolean(projectId),
  });

  useEffect(() => {
    if (projectId && !currentUserId && users.data?.[0]?.id) {
      setCurrentUserId(users.data[0].id);
    }
  }, [projectId, currentUserId, users.data, setCurrentUserId]);

  if (!users.data) {
    return <div className="text-xs text-zinc-500">Loading users…</div>;
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-xs text-zinc-500">Impersonate</span>
      <Select value={currentUserId ?? undefined} onValueChange={setCurrentUserId}>
        <SelectTrigger className="w-56">
          <SelectValue placeholder="Select user…" />
        </SelectTrigger>
        <SelectContent>
          {users.data.map((u) => (
            <SelectItem key={u.id} value={u.id}>
              {u.display_name} <span className="ml-1 text-xs text-zinc-500">({u.role})</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
