"use client";

import { useQuery } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import type { TodayV2 } from "@/lib/types";

export function useToday(projectId: string | null) {
  return useQuery<TodayV2>({
    queryKey: ["today", projectId],
    enabled: Boolean(projectId),
    queryFn: () => {
      if (!projectId) throw new Error("projectId required");
      return apiBrowser().getToday(projectId);
    },
  });
}
