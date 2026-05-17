"use client";

/* Server-Sent Events bridge.
 *
 * Opens a single EventSource on /api/events?project_id=... per dashboard
 * mount. Celery worker -> Redis pub/sub -> /events relay -> EventSource.
 * On each event we invalidate the affected TanStack Query keys; no
 * polling.
 */

import { useImpersonationStore } from "@/stores/impersonation";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

interface ServerEvent {
  type: string;
  user_id?: string;
  day?: number;
  phase?: string;
  count?: number;
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export function useEvents(): void {
  const { currentProjectId } = useImpersonationStore();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!currentProjectId) return;
    const url = `${BASE}/events?project_id=${currentProjectId}`;
    const source = new EventSource(url);

    source.addEventListener("update", (event) => {
      let data: ServerEvent;
      try {
        data = JSON.parse((event as MessageEvent).data) as ServerEvent;
      } catch {
        return;
      }
      switch (data.type) {
        case "digest.updated":
          void queryClient.invalidateQueries({ queryKey: ["digest"] });
          void queryClient.invalidateQueries({ queryKey: ["today"] });
          break;
        case "message.synthesized":
          void queryClient.invalidateQueries({ queryKey: ["today"] });
          break;
        case "phase.changed":
          void queryClient.invalidateQueries({ queryKey: ["project"] });
          void queryClient.invalidateQueries({ queryKey: ["digest"] });
          break;
        case "decisions.updated":
          void queryClient.invalidateQueries({ queryKey: ["decisions"] });
          break;
      }
    });

    source.onerror = () => {
      // EventSource auto-reconnects with a backoff; let it handle the
      // drop instead of tearing down. If the connection genuinely dies
      // the browser will retry every ~3s.
    };

    return () => {
      source.close();
    };
  }, [currentProjectId, queryClient]);
}
