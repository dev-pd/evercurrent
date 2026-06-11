"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Minus, Plus, Target, TrendingDown, TrendingUp } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import type { FocusTopic } from "@/lib/types";

const SOURCE_META: Record<string, { label: string; cls: string }> = {
  role: { label: "role", cls: "bg-indigo-100 text-indigo-700" },
  phase: { label: "phase", cls: "bg-amber-100 text-amber-700" },
  learned: { label: "learned", cls: "bg-emerald-100 text-emerald-700" },
};

function FocusRow({
  item,
  onSignal,
  pending,
}: {
  item: FocusTopic;
  onSignal: (topic: string, delta: number) => void;
  pending: boolean;
}) {
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="flex w-40 shrink-0 items-center gap-1.5">
        <span className="truncate text-xs font-medium text-[var(--text-primary)]">
          {item.label}
        </span>
        {item.trend === "up" && <TrendingUp className="h-3 w-3 text-emerald-600" />}
        {item.trend === "down" && <TrendingDown className="h-3 w-3 text-zinc-400" />}
      </div>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]">
        <div
          className="h-full rounded-full bg-[var(--color-accent-500)]"
          style={{ width: `${Math.round(item.weight * 100)}%` }}
        />
      </div>
      <div className="flex w-28 shrink-0 gap-1">
        {item.sources.map((s) => (
          <span
            key={s}
            className={`rounded px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide ${SOURCE_META[s]?.cls ?? ""}`}
          >
            {SOURCE_META[s]?.label ?? s}
          </span>
        ))}
      </div>
      <div className="flex shrink-0 gap-1">
        <button
          type="button"
          aria-label={`Boost ${item.label}`}
          disabled={pending}
          onClick={() => onSignal(item.topic, 0.5)}
          className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-emerald-600 disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Mute ${item.label}`}
          disabled={pending}
          onClick={() => onSignal(item.topic, -0.5)}
          className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-zinc-700 disabled:opacity-50"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function FocusPanel() {
  const as = useSearchParams().get("as");
  const qc = useQueryClient();
  const key = ["focus", as] as const;

  const { data: focus = [] } = useQuery({
    queryKey: key,
    queryFn: () => apiBrowser().getFocus(),
    staleTime: 30_000,
  });

  const signal = useMutation({
    mutationFn: ({ topic, delta }: { topic: string; delta: number }) =>
      apiBrowser().focusSignal(topic, delta),
    onSuccess: (data) => qc.setQueryData(key, data),
  });

  if (focus.length === 0) return null;

  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-white px-5 py-3">
      <div className="mb-1 flex items-center gap-2">
        <Target className="h-3.5 w-3.5 text-[var(--color-accent-600)]" aria-hidden="true" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Your focus
        </h2>
        <span className="text-[11px] text-[var(--text-muted)]">
          role + phase + how you&apos;ve been engaging · tune it
        </span>
      </div>
      <div className="divide-y divide-[var(--border-default)]">
        {focus.map((item) => (
          <FocusRow
            key={item.topic}
            item={item}
            pending={signal.isPending}
            onSignal={(topic, delta) => signal.mutate({ topic, delta })}
          />
        ))}
      </div>
    </div>
  );
}
