"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Cloud, Loader2, MessageSquare, RefreshCw, Unplug } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { messages } from "@/lib/messages";
import type { ConnectorSummary } from "@/lib/types";

const copy = messages.sources;

const SOURCES = [
  { kind: "slack", label: "Slack", desc: copy.slackDesc, icon: MessageSquare },
  { kind: "dropbox", label: "Dropbox", desc: copy.dropboxDesc, icon: Cloud },
] as const;

const SYNC_POLL_INTERVAL_MS = 10_000;
const SYNC_POLL_TICKS = 18;

interface SourcesCardProps {
  connectors: ConnectorSummary[];
}

export function SourcesCard({ connectors }: SourcesCardProps) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function connect(kind: "slack" | "dropbox") {
    setBusy(kind);
    setError(null);
    try {
      const { redirect_url } = await apiBrowser().startInstall(kind);
      window.location.assign(redirect_url);
    } catch {
      setError(copy.failed(kind));
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Sources</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-white">
        {SOURCES.map((source, index) => {
          const connector = connectors.find((candidate) => candidate.kind === source.kind);
          const connected = !!connector && connector.status === "active";
          const Icon = source.icon;
          return (
            <div
              key={source.kind}
              className={`flex items-center justify-between gap-3 p-4 ${
                index > 0 ? "border-t border-[var(--border-default)]" : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-secondary)]">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {source.label}
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {connected
                      ? source.kind === "slack"
                        ? copy.channels(connector.channels_count)
                        : copy.connected
                      : source.desc}
                  </span>
                </div>
              </div>
              {connected ? (
                <div className="flex items-center gap-2">
                  {source.kind === "slack" && <SyncButton connectorId={connector.id} />}
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                    <Check className="h-3 w-3" /> {copy.connected}
                  </span>
                  <DisconnectButton connectorId={connector.id} label={source.label} />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => connect(source.kind)}
                  disabled={busy === source.kind}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--color-accent-700)] disabled:opacity-60"
                >
                  {busy === source.kind && <Loader2 className="h-4 w-4 animate-spin" />}
                  {copy.connect}
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

interface SyncButtonProps {
  connectorId: string;
}

function SyncButton({ connectorId }: SyncButtonProps) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "syncing" | "done">("idle");
  const [label, setLabel] = useState("Sync");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clear the background-sync poll if the component unmounts mid-poll.
  useEffect(() => () => clearPoll(), []);

  function clearPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function sync() {
    setState("syncing");
    try {
      await apiBrowser().syncSlack(connectorId);
      setLabel("Syncing in background…");
      setState("done");
      let ticks = 0;
      pollRef.current = setInterval(() => {
        router.refresh();
        if (++ticks >= SYNC_POLL_TICKS) {
          clearPoll();
          setState("idle");
          setLabel("Sync");
        }
      }, SYNC_POLL_INTERVAL_MS);
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

interface DisconnectButtonProps {
  connectorId: string;
  label: string;
}

function DisconnectButton({ connectorId, label }: DisconnectButtonProps) {
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
