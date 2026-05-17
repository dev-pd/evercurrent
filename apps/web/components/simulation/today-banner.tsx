"use client";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, RefreshCw, Sparkles } from "lucide-react";

const REFRESH_INTERVAL_MS = 15_000;

function relativeTime(iso: string | null): string {
  if (!iso) return "never";
  const diffMs = Date.now() - new Date(iso).getTime();
  if (diffMs < 60_000) return `${Math.max(1, Math.round(diffMs / 1000))}s ago`;
  if (diffMs < 3600_000) return `${Math.round(diffMs / 60_000)}m ago`;
  return `${Math.round(diffMs / 3600_000)}h ago`;
}

export function TodayBanner() {
  const { currentProjectId, currentDay, setCurrentDay } = useImpersonationStore();
  const queryClient = useQueryClient();

  const today = useQuery({
    queryKey: ["today", currentProjectId],
    queryFn: () => api.getToday(currentProjectId!),
    enabled: Boolean(currentProjectId),
    // Poll every 15s so the dashboard reflects the worker's cron sweeps.
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const refresh = useMutation({
    mutationFn: () => api.refreshToday(currentProjectId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest"] });
      void queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });

  const synthesize = useMutation({
    mutationFn: () => api.synthesizeTodayMessage(currentProjectId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });

  if (!today.data) {
    return (
      <div className="border-b border-zinc-200 bg-emerald-50 px-6 py-2 text-xs">
        <Spinner size="xs" label="Loading live status…" />
      </div>
    );
  }

  const onToday = currentDay === today.data.live_day;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-xs text-emerald-900">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-white uppercase">
          <Activity className="h-3 w-3 animate-pulse" />
          Live
        </span>
        <span className="font-medium">Today is day {today.data.live_day}</span>
        <span>·</span>
        <span>{today.data.message_count} message(s) in today&apos;s bucket</span>
        <span>·</span>
        <span>last message {relativeTime(today.data.last_message_at)}</span>
        <span>·</span>
        <span>last digest refresh {relativeTime(today.data.last_digest_generated_at)}</span>
      </div>
      <div className="flex items-center gap-2">
        {!onToday && (
          <Button
            variant="outline"
            size="sm"
            className="h-7 border-emerald-300 bg-white text-emerald-900"
            onClick={() => setCurrentDay(today.data!.live_day)}
          >
            Jump to today
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          className="h-7 border-emerald-300 bg-white text-emerald-900"
          onClick={() => synthesize.mutate()}
          disabled={synthesize.isPending}
        >
          {synthesize.isPending ? <Spinner size="xs" /> : <Sparkles className="h-3 w-3" />}
          Inject a new message
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-7 border-emerald-300 bg-white text-emerald-900"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
        >
          {refresh.isPending ? <Spinner size="xs" /> : <RefreshCw className="h-3 w-3" />}
          Refresh now
        </Button>
      </div>
    </div>
  );
}
