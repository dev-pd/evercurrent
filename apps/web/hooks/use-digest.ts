"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import type { DigestV2, RegenerateResponse } from "@/lib/types";

export function useDigest(initialData?: DigestV2) {
  return useQuery<DigestV2>({
    queryKey: ["digest"],
    queryFn: () => apiBrowser().getDigestToday(),
    initialData,
  });
}

export function useRegenerateDigest() {
  const queryClient = useQueryClient();
  return useMutation<RegenerateResponse, Error, void>({
    mutationFn: () => apiBrowser().regenerateDigest(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digest"] });
    },
  });
}
