"use client";

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { messages } from "@/lib/messages";
import { useEve } from "@/stores/eve";
import { useToast } from "@/stores/toast";

const copy = messages.insights;

export function GenerateInsightButton({ hasData = false }: { hasData?: boolean }) {
  const toast = useToast();
  const running = useEve((s) => s.running);
  const start = useEve((s) => s.start);
  const done = useEve((s) => s.done);
  const [error, setError] = useState<string | null>(null);

  // running lives in a global store + the app-shell EveStreamListener clears it
  // on the SSE result, so "investigating" survives page navigation and only
  // ends when the backend actually finishes (or the store's safety timeout).
  async function run() {
    setError(null);
    start();
    try {
      await apiBrowser().generateInsight();
      toast.show(copy.eveStarted, "info");
    } catch {
      done();
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
