"use client";

import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { useEffect, useRef } from "react";

const TODAY_POLL_MS = 10_000;

function relativeTime(iso: string | null): string {
  if (!iso) return "never";
  const diffMs = Date.now() - new Date(iso).getTime();
  if (diffMs < 60_000) return `${Math.max(1, Math.round(diffMs / 1000))}s ago`;
  if (diffMs < 3600_000) return `${Math.round(diffMs / 60_000)}m ago`;
  return `${Math.round(diffMs / 3600_000)}h ago`;
}

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function TodayBanner() {
  const { currentProjectId } = useImpersonationStore();
  const queryClient = useQueryClient();
  const lastDigestSeen = useRef<string | null>(null);

  const today = useQuery({
    queryKey: ["today", currentProjectId],
    queryFn: () => api.getToday(currentProjectId!),
    enabled: Boolean(currentProjectId),
    refetchInterval: TODAY_POLL_MS,
  });

  // When the worker writes a fresh digest, /today's
  // last_digest_generated_at moves. Invalidate the dashboard's digest
  // query so the user sees the new ranking without a manual reload.
  const lastDigestAt = today.data?.last_digest_generated_at ?? null;
  useEffect(() => {
    if (!lastDigestAt) return;
    if (lastDigestSeen.current === lastDigestAt) return;
    lastDigestSeen.current = lastDigestAt;
    void queryClient.invalidateQueries({ queryKey: ["digest"] });
  }, [lastDigestAt, queryClient]);

  if (!today.data) {
    return (
      <div className="border-b border-zinc-200 bg-emerald-50 px-6 py-2 text-xs">
        <Spinner size="xs" label="Loading live status…" />
      </div>
    );
  }

  const liveDateText = formatDate(today.data.live_date);

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-xs text-emerald-900">
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-white uppercase">
        <Activity className="h-3 w-3 animate-pulse" />
        Live
      </span>
      <span className="font-medium">{liveDateText}</span>
      <span>·</span>
      <span>phase {today.data.phase}</span>
      <span>·</span>
      <span>{today.data.message_count} messages today</span>
      <span>·</span>
      <span>last inbound {relativeTime(today.data.last_message_at)}</span>
      <span>·</span>
      <span>digest refreshed {relativeTime(today.data.last_digest_generated_at)}</span>
      <span className="ml-auto text-emerald-700">
        Worker re-ranks every 30s; new Slack-style messages arrive every minute.
      </span>
    </div>
  );
}
