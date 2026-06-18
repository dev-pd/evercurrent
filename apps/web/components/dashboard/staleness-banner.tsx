import { AlertTriangle } from "lucide-react";
import { messages } from "@/lib/messages";

const copy = messages.digest;

interface StalenessBannerProps {
  resolvedSignals: number;
  newMessages: number;
}

/**
 * Informational notice that the digest has drifted since generation. The
 * Regenerate action lives once in the context bar — this only nudges.
 */
export function StalenessBanner({ resolvedSignals, newMessages }: StalenessBannerProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      role="status"
      aria-live="polite"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
      <span className="flex-1">{copy.staleBanner(resolvedSignals, newMessages)}</span>
    </div>
  );
}
