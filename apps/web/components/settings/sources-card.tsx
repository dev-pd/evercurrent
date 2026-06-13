"use client";

import { useState } from "react";
import { Check, Cloud, Loader2, MessageSquare } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import type { ConnectorSummary } from "@/lib/types";

const SOURCES = [
  { kind: "slack", label: "Slack", desc: "Ingest channel messages", icon: MessageSquare },
  { kind: "dropbox", label: "Dropbox", desc: "Ingest spec PDFs", icon: Cloud },
] as const;

export function SourcesCard({ connectors }: { connectors: ConnectorSummary[] }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function connect(kind: "slack" | "dropbox") {
    setBusy(kind);
    setError(null);
    try {
      const { redirect_url } = await apiBrowser().startInstall(kind);
      window.location.assign(redirect_url);
    } catch {
      setError(`Could not start ${kind} connection (is it configured?).`);
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Sources</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
        {SOURCES.map((s, i) => {
          const connector = connectors.find((c) => c.kind === s.kind);
          const connected = !!connector && connector.status === "active";
          const Icon = s.icon;
          return (
            <div
              key={s.kind}
              className={`flex items-center justify-between gap-3 p-4 ${
                i > 0 ? "border-t border-[var(--border-default)]" : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-secondary)]">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-[var(--text-primary)]">{s.label}</span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {connected
                      ? `Connected · ${connector.channels_count} channel${
                          connector.channels_count === 1 ? "" : "s"
                        }`
                      : s.desc}
                  </span>
                </div>
              </div>
              {connected ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                  <Check className="h-3 w-3" /> Connected
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => connect(s.kind)}
                  disabled={busy === s.kind}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--color-accent-700)] disabled:opacity-60"
                >
                  {busy === s.kind && <Loader2 className="h-4 w-4 animate-spin" />}
                  Connect
                </button>
              )}
            </div>
          );
        })}
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </section>
  );
}
