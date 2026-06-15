"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Cloud, Loader2, MessageSquare, RefreshCw, Unplug } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { messages } from "@/lib/messages";
import type { ConnectorSummary } from "@/lib/types";

const t = messages.sources;

const SOURCES = [
  { kind: "slack", label: "Slack", desc: t.slackDesc, icon: MessageSquare },
  { kind: "dropbox", label: "Dropbox", desc: t.dropboxDesc, icon: Cloud },
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
      setError(t.failed(kind));
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
                      ? s.kind === "slack"
                        ? `Connected · ${connector.channels_count} channel${
                            connector.channels_count === 1 ? "" : "s"
                          }`
                        : "Connected"
                      : s.desc}
                  </span>
                </div>
              </div>
              {connected ? (
                <div className="flex items-center gap-2">
                  {s.kind === "slack" && <SyncButton connectorId={connector.id} />}
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                    <Check className="h-3 w-3" /> Connected
                  </span>
                  <DisconnectButton connectorId={connector.id} label={s.label} />
                </div>
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

function SyncButton({ connectorId }: { connectorId: string }) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "syncing" | "done">("idle");
  const [label, setLabel] = useState("Sync");

  async function sync() {
    setState("syncing");
    try {
      await apiBrowser().syncSlack(connectorId);
      setLabel("Syncing in background…");
      setState("done");
      let ticks = 0;
      const poll = setInterval(() => {
        router.refresh();
        if (++ticks >= 18) {
          clearInterval(poll);
          setState("idle");
          setLabel("Sync");
        }
      }, 10000);
    } catch {
      setLabel("Failed");
      setState("idle");
    }
  }

  return (
    <button
      type="button"
      onClick={sync}
      disabled={state === "syncing"}
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
    >
      {state === "syncing" ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <RefreshCw className="h-3.5 w-3.5" />
      )}
      {state === "syncing" ? "Syncing…" : label}
    </button>
  );
}

function DisconnectButton({ connectorId, label }: { connectorId: string; label: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function disconnect() {
    if (!window.confirm(`Disconnect ${label}? Ingested data is kept; re-connect anytime.`)) {
      return;
    }
    setBusy(true);
    try {
      await apiBrowser().disconnect(connectorId);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={disconnect}
      disabled={busy}
      aria-label={`Disconnect ${label}`}
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unplug className="h-3.5 w-3.5" />}
      Disconnect
    </button>
  );
}
