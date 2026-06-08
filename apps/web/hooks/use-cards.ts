"use client";

import { useQuery } from "@tanstack/react-query";
import { apiBrowser, type CardFilters } from "@/lib/api";
import type { CardListItem, CardResponse } from "@/lib/types";

export function useCards(filters?: CardFilters, initialData?: CardListItem[]) {
  return useQuery<CardListItem[]>({
    queryKey: ["cards", filters?.projectId, filters?.kind, filters?.status],
    queryFn: () => apiBrowser().listCards(filters),
    initialData,
  });
}

export function useCard(id: string | null, initialData?: CardResponse) {
  return useQuery<CardResponse>({
    queryKey: ["card", id],
    enabled: Boolean(id),
    initialData,
    queryFn: () => {
      if (!id) throw new Error("id required");
      return apiBrowser().getCard(id);
    },
  });
}
