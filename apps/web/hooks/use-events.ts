"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { getStreamUrl } from "@/lib/api";
import { useRegen } from "@/stores/regen";

export type StreamEventType =
  | "message_tagged"
  | "signal_created"
  | "signal_resolved"
  | "digest_regen_enqueued"
  | "digest_ready"
  | "insight_created"
  | "insight_failed";

export interface StreamEvent {
  type: StreamEventType;
  payload: Record<string, unknown>;
}

interface UseEventsOptions {
  projectId: string | null;
  onEvent?: (event: StreamEvent) => void;
  enabled?: boolean;
}

export function useEvents({ projectId, onEvent, enabled = true }: UseEventsOptions) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const regenDone = useRegen((s) => s.done);
  const sourceRef = useRef<EventSource | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled || !projectId) return;
    if (typeof window === "undefined" || typeof EventSource === "undefined") return;

    const source = new EventSource(getStreamUrl(projectId), {
      withCredentials: true,
    });
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    source.onmessage = (raw) => {
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(raw.data) as StreamEvent;
      } catch {
        return;
      }
      if (!parsed?.type) return;

      switch (parsed.type) {
        case "message_tagged":
          queryClient.invalidateQueries({ queryKey: ["today", projectId] });
          break;
        case "signal_created":
          // Signals are server-rendered too; debounce a refresh so a burst
          // of new messages collapses into one re-render (~1.5s of quiet).
          queryClient.invalidateQueries({ queryKey: ["signals", projectId] });
          if (refreshTimer.current) clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(() => router.refresh(), 1500);
          break;
        case "signal_resolved":
          // A resolved signal leaves the open boards and lands under Resolved;
          // refresh the digest too so the staleness banner re-evaluates.
          queryClient.invalidateQueries({ queryKey: ["signals", projectId] });
          queryClient.invalidateQueries({ queryKey: ["digest"] });
          if (refreshTimer.current) clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(() => router.refresh(), 1500);
          break;
        case "digest_ready":
          // The digest is server-rendered (page.tsx props), so query
          // invalidation is a no-op — refresh the server tree to re-fetch it.
          regenDone();
          queryClient.invalidateQueries({ queryKey: ["digest"] });
          router.refresh();
          break;
      }
      onEventRef.current?.(parsed);
    };

    return () => {
      source.close();
      sourceRef.current = null;
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      setConnected(false);
    };
  }, [projectId, enabled, queryClient, router, regenDone]);

  return { connected };
}
