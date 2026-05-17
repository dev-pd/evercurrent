"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import type { DigestItem } from "@/lib/types";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// LLM-generated digests cite source messages as [msg_<uuid>]. UUIDs mean
// nothing to a human reader; we swap them for "[channel · author]" using
// the hydrated item list, falling back to a short id if we can't resolve.
function humaniseCitations(markdown: string, items: DigestItem[]): string {
  if (!items.length) return markdown;
  const byId = new Map(items.map((i) => [i.id, i]));
  return markdown.replace(/\[msg_([0-9a-fA-F-]{8,})\]/g, (_match, rawId: string) => {
    const item = byId.get(rawId);
    if (!item) return `[${rawId.slice(0, 6)}…]`;
    return `[${item.channel} · ${item.author_display_name}]`;
  });
}

export function DigestCard() {
  const { currentUserId, currentProjectId, currentDay } = useImpersonationStore();
  const queryClient = useQueryClient();
  const [pendingFeedbackId, setPendingFeedbackId] = useState<string | null>(null);

  const project = useQuery({
    queryKey: ["project", currentProjectId],
    queryFn: () => api.getProject(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });
  const currentPhase = project.data?.current_phase ?? null;

  // Digest does NOT poll on a timer. TodayBanner polls /today every 10s
  // and invalidates this query whenever the worker writes a fresh digest
  // (last_digest_generated_at moves). One small heartbeat call drives the
  // whole dashboard; the per-user digest fetch only fires when there's
  // actually new content to deliver. Production: replace /today poll
  // with an SSE channel that pushes "digest.updated" events from a
  // Celery task -> Redis pub/sub -> /events endpoint.
  const digest = useQuery({
    queryKey: ["digest", currentUserId, currentDay, currentProjectId, currentPhase],
    queryFn: () => api.getDigest(currentUserId!, currentDay, currentProjectId ?? undefined),
    enabled: Boolean(currentUserId) && Boolean(currentPhase),
    retry: false,
  });

  // Cold-start path: the GET endpoint falls back to the most-recent
  // digest when no row exists for the active phase. Detect that gap and
  // enqueue a precompute for the missing cell, then poll the job and
  // refetch. Cache hit on the next phase swap is instant.
  const coldStart = useMutation({
    mutationFn: async () => {
      const job = await api.enqueueRegenerate(currentUserId!, currentProjectId!, currentDay);
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        const status = await api.getJob(job.job_id);
        if (
          status.status === "complete" ||
          status.status === "not_found" ||
          status.status === "failure" ||
          status.status === "revoked"
        )
          return status;
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      throw new Error("cold-start precompute timed out");
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest", currentUserId] });
    },
  });

  const phaseMismatch = digest.data && currentPhase ? digest.data.phase !== currentPhase : false;

  // Kick off the cold-start exactly once per (user, day, phase) cell.
  const seenMismatchKey = useRef<string | null>(null);
  useEffect(() => {
    if (!phaseMismatch || !currentPhase || !currentUserId) return;
    const key = `${currentUserId}:${currentDay}:${currentPhase}`;
    if (seenMismatchKey.current === key) return;
    seenMismatchKey.current = key;
    coldStart.mutate();
  }, [phaseMismatch, currentPhase, currentUserId, currentDay, coldStart]);

  const generate = useMutation({
    mutationFn: () => api.generateDigests(currentProjectId!, currentDay),
  });

  // Regenerate is fully queue-driven: API enqueues onto Celery + returns
  // a task_id; we poll /jobs/{id} until the worker finishes. The UI stays
  // responsive, the LLM call runs in the worker pool, and every click
  // queues a fresh task (no dedup against completed results).
  const regenerate = useMutation({
    mutationFn: async () => {
      const job = await api.enqueueRegenerate(currentUserId!, currentProjectId!, currentDay);
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        const status = await api.getJob(job.job_id);
        if (
          status.status === "complete" ||
          status.status === "not_found" ||
          status.status === "failure" ||
          status.status === "revoked"
        )
          return status;
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      throw new Error("regenerate timed out");
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest", currentUserId] });
    },
  });

  // Feedback only bumps user.topic_weights server-side. Nothing on-demand:
  // the next Regenerate click (or the next precompute sweep) picks up the
  // weight delta. Keeps the UI snappy.
  const feedback = useMutation({
    mutationFn: async (args: { messageId: string; signal: 1 | -1 }) => {
      setPendingFeedbackId(args.messageId);
      try {
        await api.postFeedback({
          userId: currentUserId!,
          messageId: args.messageId,
          signal: args.signal,
        });
      } finally {
        setPendingFeedbackId(null);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  if (!currentUserId) {
    return <p className="p-6 text-sm text-zinc-500">Select a user above.</p>;
  }

  if (digest.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No digest yet for day {currentDay}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm text-zinc-500">
            Trigger generation; it will run in the worker (~10–60s depending on rate limits + day
            size).
          </p>
          <div>
            <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
              {generate.isPending ? (
                <>
                  <Spinner size="xs" /> Enqueuing…
                </>
              ) : (
                "Generate digests"
              )}
            </Button>
          </div>
          {generate.isSuccess && (
            <p className="text-xs text-zinc-500">
              Enqueued. Refresh in ~30s. job_id: {generate.data.job_id}
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  if (digest.isLoading || !digest.data) {
    return (
      <Card>
        <CardContent className="p-6">
          <Spinner label="Loading digest…" />
        </CardContent>
      </Card>
    );
  }

  const data = digest.data;
  const regenerating = regenerate.isPending || feedback.isPending || coldStart.isPending;
  const showingMismatch = phaseMismatch && !regenerating;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle>Day {data.day} briefing</CardTitle>
          <p className="text-xs text-zinc-500">
            generated {new Date(data.generated_at).toLocaleString()}
            <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] tracking-wide text-zinc-700 uppercase">
              phase: {data.phase}
            </span>
            {regenerating && (
              <span className="ml-2 inline-flex">
                <Spinner size="xs" label="Re-ranking…" />
              </span>
            )}
            {showingMismatch && (
              <span className="ml-2 text-amber-700">
                Showing cached {data.phase} — {currentPhase} variant building in the queue.
              </span>
            )}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => regenerate.mutate()}
          disabled={regenerating}
        >
          {regenerate.isPending ? (
            <>
              <Spinner size="xs" /> Regenerating…
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4" /> Regenerate
            </>
          )}
        </Button>
      </CardHeader>
      <CardContent>
        <article className="prose prose-sm prose-zinc max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {humaniseCitations(data.content_md, data.items)}
          </ReactMarkdown>
        </article>
        {data.items.length > 0 && (
          <div className="mt-6 border-t border-zinc-200 pt-4">
            <p className="mb-1 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
              Rate the prioritisation
            </p>
            <p className="mb-3 text-xs text-zinc-500">
              Thumbs up boosts that topic for you; thumbs down dampens it. Click Regenerate above to
              see the re-ranked digest.
            </p>
            <ul className="flex flex-col gap-2">
              {data.items.map((item) => {
                const isPending = pendingFeedbackId === item.id;
                const urgency = item.urgency ?? "low";
                const urgencyColor =
                  urgency === "critical"
                    ? "bg-red-100 text-red-800"
                    : urgency === "high"
                      ? "bg-amber-100 text-amber-800"
                      : urgency === "medium"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-zinc-100 text-zinc-600";
                return (
                  <li
                    key={item.id}
                    className="flex items-start gap-3 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                        <span className="font-medium text-zinc-700">{item.channel}</span>
                        <span>·</span>
                        <span>{item.author_display_name}</span>
                        <span>·</span>
                        <span>day {item.day}</span>
                        {item.topic && (
                          <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] tracking-wide text-zinc-700 uppercase">
                            {item.topic}
                          </span>
                        )}
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${urgencyColor}`}
                        >
                          {urgency}
                        </span>
                      </div>
                      <p className="line-clamp-3 text-zinc-700">{item.text}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={() => feedback.mutate({ messageId: item.id, signal: 1 })}
                        disabled={regenerating}
                        aria-label="Thumbs up"
                      >
                        <ThumbsUp className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={() => feedback.mutate({ messageId: item.id, signal: -1 })}
                        disabled={regenerating}
                        aria-label="Thumbs down"
                      >
                        <ThumbsDown className="h-4 w-4" />
                      </Button>
                      {isPending && <Spinner size="xs" />}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
