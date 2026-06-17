"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { InsightCard } from "@/components/insights/insight-card";
import { messages } from "@/lib/messages";
import { useInsightModal } from "@/stores/insight-modal";

const copy = messages.insights;

export function InsightModal() {
  const insight = useInsightModal((s) => s.insight);
  const close = useInsightModal((s) => s.close);

  useEffect(() => {
    if (!insight) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [insight, close]);

  if (!insight) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={close}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-[2px]"
    >
      <div
        onClick={(e) => {
          e.stopPropagation();
          if ((e.target as HTMLElement).closest("a")) close();
        }}
        className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-[var(--border-default)] px-4 py-2.5">
          <span className="text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">
            {copy.modalLabel}
          </span>
          <button
            type="button"
            onClick={close}
            aria-label="Close"
            className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <InsightCard insight={insight} />
        </div>
      </div>
    </div>
  );
}
