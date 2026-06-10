"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import type { RegenerateResponse } from "@/lib/types";

export function useRegenerateDigest() {
  const queryClient = useQueryClient();
  return useMutation<RegenerateResponse, Error, void>({
    mutationFn: () => apiBrowser().regenerateDigest(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
  });
}
