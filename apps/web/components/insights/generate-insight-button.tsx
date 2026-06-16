"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { EVE_JOB_TIMEOUT_MS } from "@/lib/constants";
import { messages } from "@/lib/messages";
import { useEvents } from "@/hooks/use-events";

const copy = messages.insights;

export function GenerateInsightButton({ projectId }: { projectId: string | null }) {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function stop() {
    if (timer.current) clearTimeout(timer.current);
    setRunning(false);
  }

  // Eve runs on the worker (50-90s) and pushes the result over SSE. Keep
  // listening whenever the page is open — not only while `running` — so a
  // result that lands after the safety timeout still clears the UI.
  useEvents({
    projectId,
    enabled: !!projectId,
    onEvent: (e) => {
      if (e.type === "insight_created") {
        stop();
        setError(null);
        router.refresh();
      } else if (e.type === "insight_failed") {
        stop();
        setError(running ? copy.eveNothing : null);
      }
    },
  });

  useEffect(() => () => stop(), []);

  async function run() {
    setError(null);
    setRunning(true);
    timer.current = setTimeout(() => {
      stop();
      setError(copy.eveSlow);
    }, EVE_JOB_TIMEOUT_MS);
    try {
      await apiBrowser().generateInsight();
    } catch {
      stop();
      setError(copy.eveStartFailed);
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
        {running ? copy.eveInvestigating : copy.runEve}
      </button>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </div>
  );
}
