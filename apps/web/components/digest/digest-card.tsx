"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function DigestCard() {
  const { currentUserId, currentProjectId, currentDay } = useImpersonationStore();
  const queryClient = useQueryClient();

  const digest = useQuery({
    queryKey: ["digest", currentUserId, currentDay],
    queryFn: () => api.getDigest(currentUserId!, currentDay),
    enabled: Boolean(currentUserId),
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () => api.generateDigests(currentProjectId!, currentDay),
  });

  const feedback = useMutation({
    mutationFn: (args: { messageId: string; signal: 1 | -1 }) =>
      api.postFeedback({ userId: currentUserId!, messageId: args.messageId, signal: args.signal }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["digest", currentUserId] });
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
              {generate.isPending ? "Enqueuing…" : "Generate digests"}
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
    return <p className="p-6 text-sm text-zinc-500">Loading digest…</p>;
  }

  const data = digest.data;
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle>Day {data.day} briefing</CardTitle>
          <p className="text-xs text-zinc-500">
            generated {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
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
            <div className="flex flex-wrap gap-2">
              {data.item_message_ids.slice(0, 6).map((mid) => (
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
                    aria-label="Thumbs up"
                  >
                    <ThumbsUp className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => feedback.mutate({ messageId: mid, signal: -1 })}
                    aria-label="Thumbs down"
                  >
                    <ThumbsDown className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
