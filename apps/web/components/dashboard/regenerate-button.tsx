"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRegenerateDigest } from "@/hooks/use-digest";

export function RegenerateButton() {
  const mutation = useRegenerateDigest();

  return (
    <Button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      variant="outline"
      size="sm"
    >
      {mutation.isPending ? (
        <Spinner size="xs" />
      ) : (
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      Regenerate
    </Button>
  );
}
