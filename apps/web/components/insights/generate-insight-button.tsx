"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { EVE_JOB_TIMEOUT_MS } from "@/lib/constants";
import { messages } from "@/lib/messages";
import { useEvents } from "@/hooks/use-events";
import { useToast } from "@/stores/toast";

const copy = messages.insights;

export function GenerateInsightButton({
  projectId,
  hasData = false,
}: {
  projectId: string | null;
  hasData?: boolean;
}) {
  const router = useRouter();
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshingRef = useRef(false);

  function stop() {
    if (timer.current) clearTimeout(timer.current);
    setRunning(false);
  }

  // Toast only after the refresh transition settles (the insight has rendered),
  // so the success toast doesn't beat the insight onto the page.
  useEffect(() => {
    if (isPending || !refreshingRef.current) return;
    refreshingRef.current = false;
    toast.show(copy.insightReady, "success");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPending]);

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
        refreshingRef.current = true;
        startTransition(() => router.refresh());
      } else if (e.type === "insight_failed") {
        stop();
        setError(running ? copy.eveNothing : null);
        if (running) toast.show(copy.eveNothing, "info");
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
      toast.show(copy.eveStarted, "info");
    } catch {
      stop();
      setError(copy.eveStartFailed);
      toast.show(copy.eveStartFailed, "error");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={run}
        disabled={running || !hasData}
        title={!hasData ? copy.eveNeedsData : undefined}
        className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-accent-700)] disabled:opacity-60"
      >
        {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        {running ? copy.eveInvestigating : copy.runEve}
      </button>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </div>
  );
}
