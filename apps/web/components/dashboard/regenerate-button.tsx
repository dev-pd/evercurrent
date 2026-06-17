"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRegenerateDigest } from "@/hooks/use-digest";
import { useRegen } from "@/stores/regen";
import { useToast } from "@/stores/toast";
import { messages } from "@/lib/messages";

const copy = messages.dashboard;

export function RegenerateButton() {
  const mutation = useRegenerateDigest();
  const pending = useRegen((s) => s.pending);
  const start = useRegen((s) => s.start);
  const done = useRegen((s) => s.done);
  const toast = useToast();

  const busy = mutation.isPending || pending;

  return (
    <Button
      onClick={() => {
        start();
        toast.show(copy.regenStarted, "info");
        mutation.mutate(undefined, {
          onError: () => {
            done();
            toast.show(copy.regenFailed, "error");
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
  );
}
