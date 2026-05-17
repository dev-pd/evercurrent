"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import type { DigestItem } from "@/lib/types";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
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

  const digest = useQuery({
    queryKey: ["digest", currentUserId, currentDay],
    queryFn: () => api.getDigest(currentUserId!, currentDay),
    enabled: Boolean(currentUserId),
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () => api.generateDigests(currentProjectId!, currentDay),
  });

  const regenerate = useMutation({
    mutationFn: () => api.regenerateDigest(currentUserId!, currentProjectId!, currentDay),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest", currentUserId] });
    },
  });

  const feedback = useMutation({
    mutationFn: async (args: { messageId: string; signal: 1 | -1 }) => {
      setPendingFeedbackId(args.messageId);
      try {
        await api.postFeedback({
          userId: currentUserId!,
          messageId: args.messageId,
          signal: args.signal,
        });
        // Synchronously regenerate the digest so the user sees the learned-weight
        // effect within ~5s rather than on the next refresh.
        await api.regenerateDigest(currentUserId!, currentProjectId!, currentDay);
      } finally {
        setPendingFeedbackId(null);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest", currentUserId] });
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
  const regenerating = regenerate.isPending || feedback.isPending;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle>Day {data.day} briefing</CardTitle>
          <p className="text-xs text-zinc-500">
            generated {new Date(data.generated_at).toLocaleString()}
            {regenerating && (
              <span className="ml-2 inline-flex">
                <Spinner size="xs" label="Re-ranking…" />
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
              Thumbs up boosts that topic for you; thumbs down dampens it. Digest re-ranks
              immediately (~3-10s).
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
