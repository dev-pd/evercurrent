"use client";

import { useState } from "react";
import { useDigest, useDigestList } from "@/hooks/use-digest";
import { parseDigest } from "@/lib/digest-parse";
import { messages } from "@/lib/messages";
import { DigestColumns } from "./digest-columns";
import { DigestDatePicker } from "./digest-date-picker";
import { StalenessBanner } from "./staleness-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";

const copy = messages.dashboard;
const digestCopy = messages.digest;

export function DigestView() {
  const list = useDigestList();
  const todayIndex = list.data?.today_index ?? null;

  // Default to today once the list resolves; never let the picker point at a
  // day with no stored digest (future days are simply absent from the list).
  const [selected, setSelected] = useState<number | null>(null);
  const items = list.data?.items ?? [];
  const effectiveSelected =
    selected !== null && items.some((item) => item.day_index === selected)
      ? selected
      : todayIndex;

  const digest = useDigest(effectiveSelected, todayIndex);
  const isToday = effectiveSelected !== null && effectiveSelected === todayIndex;

  if (list.isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="md" />
      </div>
    );
  }

  if (items.length === 0) {
    return <EmptyState title={copy.noDigestTitle} hint={copy.noDigestHint} />;
  }

  const data = digest.data;
  const buckets = parseDigest(data?.content_md);
  const showBanner = isToday && data?.is_stale === true;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <DigestDatePicker
          items={items}
          todayIndex={todayIndex ?? 0}
          selected={effectiveSelected ?? todayIndex ?? 0}
          onSelect={setSelected}
          disabled={digest.isFetching}
        />
        {digest.isFetching && <Spinner size="sm" />}
      </div>

      {showBanner && data && (
        <StalenessBanner
          resolvedSignals={data.stale_resolved_signals}
          newMessages={data.stale_new_messages}
        />
      )}

      {digest.isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner size="md" />
        </div>
      ) : digest.isError ? (
        <EmptyState title={digestCopy.loadError} />
      ) : (
        <DigestColumns buckets={buckets} />
      )}
    </div>
  );
}
