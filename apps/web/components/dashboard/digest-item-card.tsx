"use client";

import Link from "next/link";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFeedback, useCardFeedbackState } from "@/hooks/use-feedback";
import { cn } from "@/lib/utils";
import type { DigestItemV2 } from "@/lib/types";

export interface DigestItemCardProps {
  item: DigestItemV2;
  onFeedback?: (vars: { cardId: string; useful: boolean }) => void;
}

function formatTimestamp(ts: string | null | undefined): string | null {
  if (!ts) return null;
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export function DigestItemCard({ item, onFeedback }: DigestItemCardProps) {
  const feedback = useFeedback();
  const currentSignal = useCardFeedbackState(item.card_id ?? item.id);
  const ts = formatTimestamp(item.ts);

  const fire = (useful: boolean) => {
    const cardId = item.card_id ?? item.id;
    if (onFeedback) {
      onFeedback({ cardId, useful });
      return;
    }
    feedback.mutate({ cardId, useful });
  };

  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-1 text-xs text-zinc-500">
        <span>
          {item.source}
          {item.author_display_name ? ` · ${item.author_display_name}` : ""}
          {ts ? ` · ${ts}` : ""}
        </span>
      </div>
      <p className="mt-2 text-sm text-zinc-900">{item.why_this_matters}</p>
      <div className="mt-3 flex items-center gap-2">
        <Button
          onClick={() => fire(true)}
          disabled={feedback.isPending}
          variant={currentSignal === true ? "default" : "outline"}
          size="sm"
          aria-label="Useful"
          aria-pressed={currentSignal === true}
        >
          <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
        <Button
          onClick={() => fire(false)}
          disabled={feedback.isPending}
          variant={currentSignal === false ? "default" : "outline"}
          size="sm"
          aria-label="Not useful"
          aria-pressed={currentSignal === false}
        >
          <ThumbsDown className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
        {item.card_id && (
          <Link
            href={`/decisions/${item.card_id}`}
            className={cn(
              "ml-auto text-xs font-medium text-zinc-700 hover:text-zinc-900",
            )}
          >
            Open card
          </Link>
        )}
      </div>
    </article>
  );
}
