"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import type { CardFeedbackResponse } from "@/lib/types";

interface FeedbackVars {
  cardId: string;
  useful: boolean;
}

interface FeedbackContext {
  previous: Record<string, boolean | undefined>;
}

const FEEDBACK_KEY = ["card-feedback"] as const;

export function useCardFeedbackState(cardId: string): boolean | undefined {
  const queryClient = useQueryClient();
  const cache = queryClient.getQueryData<Record<string, boolean>>(FEEDBACK_KEY) ?? {};
  return cache[cardId];
}

export function useFeedback() {
  const queryClient = useQueryClient();
  return useMutation<CardFeedbackResponse, Error, FeedbackVars, FeedbackContext>({
    mutationFn: ({ cardId, useful }) => apiBrowser().feedbackCard(cardId, useful),
    onMutate: async ({ cardId, useful }) => {
      const previous = queryClient.getQueryData<Record<string, boolean>>(FEEDBACK_KEY) ?? {};
      queryClient.setQueryData<Record<string, boolean>>(FEEDBACK_KEY, {
        ...previous,
        [cardId]: useful,
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(FEEDBACK_KEY, context.previous);
      }
    },
  });
}
