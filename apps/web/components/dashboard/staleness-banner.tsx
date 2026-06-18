"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRegenerateDigest } from "@/hooks/use-digest";
import { useRegen } from "@/stores/regen";
import { useToast } from "@/stores/toast";
import { messages } from "@/lib/messages";

const copy = messages.digest;
const dash = messages.dashboard;

interface StalenessBannerProps {
  resolvedSignals: number;
  newMessages: number;
}

export function StalenessBanner({ resolvedSignals, newMessages }: StalenessBannerProps) {
  const mutation = useRegenerateDigest();
  const pending = useRegen((s) => s.pending);
  const start = useRegen((s) => s.start);
  const done = useRegen((s) => s.done);
  const toast = useToast();

  const busy = mutation.isPending || pending;

  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      role="status"
      aria-live="polite"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
      <span className="flex-1">{copy.staleBanner(resolvedSignals, newMessages)}</span>
      <Button
        onClick={() => {
          start();
          toast.show(dash.regenStarted, "info");
          mutation.mutate(undefined, {
            onError: () => {
              done();
              toast.show(dash.regenFailed, "error");
            },
          });
        }}
        disabled={busy}
        variant="outline"
        size="sm"
      >
        {busy ? <Spinner size="xs" /> : <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
        {busy ? copy.regenerating : copy.regenerate}
      </Button>
    </div>
  );
}
