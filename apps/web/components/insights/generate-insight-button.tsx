"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { useEvents } from "@/hooks/use-events";

export function GenerateInsightButton({ projectId }: { projectId: string | null }) {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function stop() {
    if (timer.current) clearTimeout(timer.current);
    setRunning(false);
  }

  // Eve runs on the worker (~10s) and pushes the result over SSE.
  useEvents({
    projectId,
    enabled: running,
    onEvent: (e) => {
      if (e.type === "insight_created") {
        stop();
        router.refresh();
      } else if (e.type === "insight_failed") {
        stop();
        setError("Eve found nothing worth flagging right now. Try again.");
      }
    },
  });

  useEffect(() => () => stop(), []);

  async function run() {
    setError(null);
    setRunning(true);
    timer.current = setTimeout(() => {
      stop();
      setError("Eve is taking a while — refresh in a moment to see the result.");
    }, 45_000);
    try {
      await apiBrowser().generateInsight();
    } catch {
      stop();
      setError("Could not start Eve. Try again.");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={run}
        disabled={running}
        className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-accent-700)] disabled:opacity-60"
      >
        {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        {running ? "Eve is investigating…" : "Run Eve"}
      </button>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </div>
  );
}
