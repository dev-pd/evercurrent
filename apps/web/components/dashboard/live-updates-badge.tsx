"use client";

import { useCallback, useState } from "react";
import { Bell } from "lucide-react";
import { useEvents, type StreamEvent } from "@/hooks/use-events";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import { cn } from "@/lib/utils";

const copy = messages.dashboard;

interface LiveUpdatesBadgeProps {
  projectId: string | null;
  generatedAt: string | null;
}

interface CounterState {
  generatedAt: string | null;
  count: number;
}

export function LiveUpdatesBadge({ projectId, generatedAt }: LiveUpdatesBadgeProps) {
  const [state, setState] = useState<CounterState>({ generatedAt, count: 0 });

  const visibleCount = state.generatedAt === generatedAt ? state.count : 0;
  if (state.generatedAt !== generatedAt) {
    setState({ generatedAt, count: 0 });
  }

  const handleEvent = useCallback((event: StreamEvent) => {
    if (event.type === "message_tagged" || event.type === "signal_created") {
      setState((prev) => ({ ...prev, count: prev.count + 1 }));
    } else if (event.type === "digest_ready") {
      setState((prev) => ({ ...prev, count: 0 }));
    }
  }, []);

  const { connected } = useEvents({ projectId, onEvent: handleEvent });

  const updatedAt = formatTimestamp(generatedAt, "time");

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs",
        connected
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-zinc-200 bg-zinc-50 text-zinc-500",
      )}
      role="status"
      aria-live="polite"
    >
      <Bell className="h-3 w-3" aria-hidden="true" />
      <span>{visibleCount === 0 ? copy.live : copy.newCount(visibleCount)}</span>
      {updatedAt && (
        <span className="border-l border-current/20 pl-2 opacity-70">
          {copy.updatedAt(updatedAt)}
        </span>
      )}
    </div>
  );
}
