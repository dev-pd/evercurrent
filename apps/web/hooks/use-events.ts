"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getStreamUrl } from "@/lib/api";

export type StreamEventType =
  | "message_tagged"
  | "card_created"
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
  const sourceRef = useRef<EventSource | null>(null);
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
        case "card_created":
          queryClient.invalidateQueries({ queryKey: ["cards", projectId] });
          break;
        case "digest_ready":
          queryClient.invalidateQueries({ queryKey: ["digest"] });
          break;
      }
      onEventRef.current?.(parsed);
    };

    return () => {
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [projectId, enabled, queryClient]);

  return { connected };
}
