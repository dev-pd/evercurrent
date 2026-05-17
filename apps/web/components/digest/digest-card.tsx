"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.content_md}</ReactMarkdown>
        </article>
        {data.item_message_ids.length > 0 && (
          <div className="mt-6 border-t border-zinc-200 pt-4">
            <p className="mb-2 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
              Rate the prioritisation
            </p>
            <p className="mb-3 text-xs text-zinc-500">
              Thumbs up boosts that topic for you; thumbs down dampens it. Digest re-ranks
              immediately (~3-10s).
            </p>
            <div className="flex flex-wrap gap-2">
              {data.item_message_ids.slice(0, 6).map((mid) => {
                const isPending = pendingFeedbackId === mid;
                return (
                  <div
                    key={mid}
                    className="flex items-center gap-1 rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs"
                  >
                    <span className="font-mono text-zinc-500">msg_{mid.slice(0, 8)}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => feedback.mutate({ messageId: mid, signal: 1 })}
                      disabled={regenerating}
                      aria-label="Thumbs up"
                    >
                      <ThumbsUp className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => feedback.mutate({ messageId: mid, signal: -1 })}
                      disabled={regenerating}
                      aria-label="Thumbs down"
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </Button>
                    {isPending && <Spinner size="xs" />}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
