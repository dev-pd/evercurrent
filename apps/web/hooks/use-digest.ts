"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import type { DigestList, DigestV2, RegenerateResponse } from "@/lib/types";

export function useDigestList() {
  return useQuery<DigestList>({
    queryKey: ["digests", "list"],
    queryFn: () => apiBrowser().listDigests(),
  });
}

// `dayIndex === todayIndex` is the live digest (`/digests/today`); any other day
// is a read-only past snapshot (`/digests/{dayIndex}`). A null dayIndex disables
// the query until the list resolves and a day is selected.
export function useDigest(dayIndex: number | null, todayIndex: number | null) {
  return useQuery<DigestV2>({
    queryKey: ["digest", dayIndex],
    queryFn: () =>
      dayIndex === todayIndex
        ? apiBrowser().getDigestToday()
        : apiBrowser().getDigestByDay(dayIndex as number),
    enabled: dayIndex !== null,
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
