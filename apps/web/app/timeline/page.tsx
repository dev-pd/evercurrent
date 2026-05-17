"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQueries } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DAYS = [1, 2, 3, 4, 5];

export default function TimelinePage() {
  const { currentUserId } = useImpersonationStore();
  const queries = useQueries({
    queries: DAYS.map((day) => ({
      queryKey: ["digest", currentUserId, day],
      queryFn: () => api.getDigest(currentUserId!, day),
      enabled: Boolean(currentUserId),
      retry: false,
    })),
  });

  return (
    <AppShell>
      <div className="p-6">
        <h1 className="mb-1 text-xl font-semibold">Digest timeline</h1>
        <p className="mb-6 text-sm text-zinc-500">
          5 days side-by-side. Spot when the dominant topic shifts.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          {DAYS.map((day, i) => {
            const q = queries[i];
            return (
              <Card key={day}>
                <CardHeader>
                  <CardTitle className="text-base">Day {day}</CardTitle>
                </CardHeader>
                <CardContent className="text-xs">
                  {q.isLoading && <p className="text-zinc-500">Loading…</p>}
                  {q.isError && <p className="text-zinc-500">No digest for day {day}.</p>}
                  {q.data && (
                    <article className="prose prose-xs prose-zinc max-h-[60vh] max-w-none overflow-auto">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.data.content_md}</ReactMarkdown>
                    </article>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
