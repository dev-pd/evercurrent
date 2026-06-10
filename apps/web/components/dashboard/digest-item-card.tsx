"use client";

import Link from "next/link";
import { ArrowUpRight, MessageSquare, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFeedback, useCardFeedbackState } from "@/hooks/use-feedback";
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
    <article className="group rounded-lg border border-[var(--border-default)] bg-white p-4 transition-colors hover:border-[var(--border-strong)]">
      <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
        <MessageSquare className="h-3 w-3" aria-hidden="true" />
        <span className="font-medium text-[var(--text-secondary)]">{item.source}</span>
        {item.author_display_name && (
          <>
            <span aria-hidden="true">·</span>
            <span>{item.author_display_name}</span>
          </>
        )}
        {ts && (
          <>
            <span aria-hidden="true">·</span>
            <span className="font-mono tabular-nums">{ts}</span>
          </>
        )}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-[var(--text-primary)]">
        {item.why_this_matters}
      </p>
      <div className="mt-3 flex items-center gap-1.5">
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
            className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[var(--color-accent-700)] hover:text-[var(--color-accent-800)]"
          >
            Open card
            <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        )}
      </div>
    </article>
  );
}
