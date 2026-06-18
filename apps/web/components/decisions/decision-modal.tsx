"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { SignalCard } from "@/components/signals/signal-card";
import { messages } from "@/lib/messages";
import { useDecisionModal } from "@/stores/decision-modal";

const copy = messages.decisions;

export function DecisionModal() {
  const signalId = useDecisionModal((s) => s.signalId);
  const close = useDecisionModal((s) => s.close);

  const { data: signal, isLoading } = useQuery({
    queryKey: ["signal", signalId],
    queryFn: () => apiBrowser().getSignal(signalId as string),
    enabled: !!signalId,
  });

  useEffect(() => {
    if (!signalId) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [signalId, close]);

  if (!signalId) return null;

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
          // Clicking a link inside (e.g. "Open in Slack") navigates away —
          // close the modal so its backdrop doesn't linger over the page.
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
          {isLoading || !signal ? (
            <div className="flex h-44 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-[var(--color-accent-600)]" />
            </div>
          ) : (
            <SignalCard signal={signal} />
          )}
        </div>
      </div>
    </div>
  );
}
