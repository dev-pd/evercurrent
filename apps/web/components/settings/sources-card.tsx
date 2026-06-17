"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Cloud, Loader2, MessageSquare, RefreshCw, Unplug } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { messages } from "@/lib/messages";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/stores/toast";
import type { ConnectorSummary } from "@/lib/types";

const copy = messages.sources;

const SOURCES = [
  { kind: "slack", label: "Slack", desc: copy.slackDesc, icon: MessageSquare },
  { kind: "dropbox", label: "Dropbox", desc: copy.dropboxDesc, icon: Cloud },
] as const;

const SYNC_POLL_INTERVAL_MS = 3_000;
const SYNC_POLL_MAX_TICKS = 25;
const SYNC_SETTLE_TICKS = 2;

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
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">{copy.heading}</h2>
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
                        ? copy.synced(connector.message_count, connector.channels_count)
                        : copy.documents(connector.message_count)
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
  const queryClient = useQueryClient();
  const toast = useToast();
  const [syncing, setSyncing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => clearPoll(), []);

  function clearPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function finish(memberCount: number) {
    clearPoll();
    await queryClient.invalidateQueries({ queryKey: ["members"] });
    router.refresh();
    setSyncing(false);
    toast.show(copy.syncComplete(memberCount), "success");
  }

  async function sync() {
    setSyncing(true);
    try {
      await apiBrowser().syncSlack(connectorId);
    } catch {
      setSyncing(false);
      toast.show(copy.syncFailedToast, "error");
      return;
    }
    toast.show(copy.syncStarted, "info");

    // The sync runs in a background worker (backfill + member provisioning), so
    // poll the member list and settle once it stops growing — then refresh the
    // table + switcher and toast completion.
    let ticks = 0;
    let lastCount = -1;
    let stable = 0;
    pollRef.current = setInterval(() => {
      ticks += 1;
      void apiBrowser()
        .listMembers()
        .then((members) => {
          const count = members.length;
          router.refresh();
          if (count > 0 && count === lastCount) {
            stable += 1;
          } else {
            stable = 0;
          }
          lastCount = count;
          if ((count > 0 && stable >= SYNC_SETTLE_TICKS) || ticks >= SYNC_POLL_MAX_TICKS) {
            void finish(count);
          }
        })
        .catch(() => {
          if (ticks >= SYNC_POLL_MAX_TICKS) {
            void finish(lastCount > 0 ? lastCount : 0);
          }
        });
    }, SYNC_POLL_INTERVAL_MS);
  }

  return (
    <button
      type="button"
      onClick={sync}
      disabled={syncing}
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
    >
      {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
      {syncing ? copy.syncingBackground : copy.sync}
    </button>
  );
}

interface DisconnectButtonProps {
  connectorId: string;
  label: string;
}

function DisconnectButton({ connectorId, label }: DisconnectButtonProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function disconnect() {
    setBusy(true);
    try {
      await apiBrowser().disconnect(connectorId);
      await queryClient.invalidateQueries({ queryKey: ["members"] });
      router.refresh();
      toast.show(copy.disconnected(label), "success");
    } finally {
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        disabled={busy}
        aria-label={`Disconnect ${label}`}
        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unplug className="h-3.5 w-3.5" />}
        {copy.disconnect}
      </button>
      <ConfirmDialog
        open={confirmOpen}
        title={copy.disconnectTitle(label)}
        message={copy.disconnectConfirm(label)}
        confirmLabel={copy.disconnect}
        cancelLabel={messages.common.cancel}
        destructive
        busy={busy}
        onConfirm={disconnect}
        onCancel={() => setConfirmOpen(false)}
      />
    </>
  );
}
