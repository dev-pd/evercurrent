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
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

export function ImpersonationDropdown() {
  const { currentProjectId, currentUserId, setCurrentProjectId, setCurrentUserId } =
    useImpersonationStore();
  const queryClient = useQueryClient();
  const [hydrated, setHydrated] = useState(false);

  // Avoid SSR-vs-client hydration mismatch — only read the persisted store
  // once we know we are on the client.
  useEffect(() => {
    const id = setTimeout(() => setHydrated(true), 0);
    return () => clearTimeout(id);
  }, []);

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });

  const queue = useCallback((cb: () => void) => {
    if (typeof globalThis.queueMicrotask === "function") {
      globalThis.queueMicrotask(cb);
    } else {
      void Promise.resolve().then(cb);
    }
  }, []);

  useEffect(() => {
    if (currentProjectId) return;
    const first = projects.data?.[0]?.id;
    if (!first) return;
    queue(() => setCurrentProjectId(first));
  }, [currentProjectId, projects.data, setCurrentProjectId, queue]);

  const projectId = currentProjectId ?? projects.data?.[0]?.id ?? null;

  const users = useQuery({
    queryKey: ["users", projectId],
    queryFn: () => api.listUsers(projectId!),
    enabled: Boolean(projectId),
  });

  useEffect(() => {
    if (!projectId || currentUserId) return;
    const first = users.data?.[0]?.id;
    if (!first) return;
    queue(() => setCurrentUserId(first));
  }, [projectId, currentUserId, users.data, setCurrentUserId, queue]);

  if (!hydrated || projects.isLoading) {
    return <Spinner size="xs" label="Loading…" />;
  }

  if (users.isLoading || !users.data) {
    return <Spinner size="xs" label="Loading users…" />;
  }

  const handleChange = (newId: string) => {
    setCurrentUserId(newId);
    // Invalidate every per-user query so the dashboard refetches with the
    // new X-Impersonate-User header on the next request.
    void queryClient.invalidateQueries({ queryKey: ["digest"] });
    void queryClient.invalidateQueries({ queryKey: ["decisions"] });
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-xs text-zinc-500">Impersonate</span>
      <Select value={currentUserId ?? undefined} onValueChange={handleChange}>
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
