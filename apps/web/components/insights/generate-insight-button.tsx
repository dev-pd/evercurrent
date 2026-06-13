"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { apiBrowser } from "@/lib/api";

/**
 * Runs the Eve agent on demand. Eve loops over its read tools (messages,
 * specs, decision cards), then emits one grounded cross-subsystem insight,
 * which the server persists. We refresh the route to show it.
 */
export function GenerateInsightButton() {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      await apiBrowser().generateInsight();
      router.refresh();
    } catch {
      setError("Eve could not produce an insight. Try again.");
    } finally {
      setRunning(false);
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
