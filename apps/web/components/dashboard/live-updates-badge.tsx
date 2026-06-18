"use client";

import { useEvents } from "@/hooks/use-events";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";

const copy = messages.dashboard;

interface LiveUpdatesBadgeProps {
  projectId: string | null;
  generatedAt: string | null;
}

export function LiveUpdatesBadge({ projectId, generatedAt }: LiveUpdatesBadgeProps) {
  // Keep the SSE subscription alive — it drives query invalidation across the
  // app (members, signals, digest). The badge itself just shows when the digest
  // was last refreshed; no live counter (that count was confusing).
  useEvents({ projectId });

  if (!generatedAt) return null;

  return (
    <span className="inline-flex items-center rounded-full border border-[var(--border-default)] bg-white px-3 py-1 text-xs text-[var(--text-muted)]">
      {copy.updatedAt(formatTimestamp(generatedAt, "datetime") ?? generatedAt)}
    </span>
  );
}
