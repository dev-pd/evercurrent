"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Cloud, Loader2, MessageSquare, RefreshCw, Unplug } from "lucide-react";
import { apiBrowser } from "@/lib/api";
import { useEvents } from "@/hooks/use-events";
import { messages } from "@/lib/messages";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/stores/toast";
import type { ConnectorSummary } from "@/lib/types";

const copy = messages.sources;

const SOURCES = [
  { kind: "slack", label: "Slack", desc: copy.slackDesc, icon: MessageSquare },
  { kind: "dropbox", label: "Dropbox", desc: copy.dropboxDesc, icon: Cloud },
] as const;

// Safety net if the sync_complete SSE never arrives (worker died, lost stream).
const SYNC_SAFETY_MS = 90_000;

interface SourcesCardProps {
  connectors: ConnectorSummary[];
  projectId: string | null;
}

export function SourcesCard({ connectors, projectId }: SourcesCardProps) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<Record<string, boolean>>({});

  function setSyncingKind(kind: string, value: boolean) {
    setSyncing((prev) => ({ ...prev, [kind]: value }));
  }

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
                    {!connected
                      ? source.desc
                      : syncing[source.kind]
                        ? copy.syncing
                        : source.kind === "slack"
                          ? copy.synced(connector.message_count, connector.channels_count)
                          : copy.documents(connector.message_count)}
                  </span>
                </div>
              </div>
              {connected ? (
                <div className="flex items-center gap-2">
                  <SyncButton
                    connectorId={connector.id}
                    kind={source.kind}
                    projectId={projectId}
                    onSyncingChange={(v) => setSyncingKind(source.kind, v)}
                  />
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
  kind: "slack" | "dropbox";
  projectId: string | null;
  onSyncingChange: (syncing: boolean) => void;
}

function SyncButton({ connectorId, kind, projectId, onSyncingChange }: SyncButtonProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [syncing, setSyncing] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finishedRef = useRef(true);

  function setState(value: boolean) {
    setSyncing(value);
    onSyncingChange(value);
  }

  // Settle when the worker finishes (sync_complete SSE) — not on a member-count
  // poll, which settled before backfill finished and made the counts jump. We
  // also don't refresh mid-sync, so the count only updates once, to its final
  // value. A safety timeout covers a missed event.
  const finish = useCallback(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    if (timer.current) clearTimeout(timer.current);
    void queryClient.invalidateQueries({ queryKey: ["members"] });
    router.refresh();
    setState(false);
    toast.show(copy.syncDone, "success");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryClient, router, toast]);

  useEvents({
    projectId,
    enabled: syncing && !!projectId,
    onEvent: (event) => {
      if (event.type === "sync_complete") {
        finish();
      }
    },
  });

  async function sync() {
    finishedRef.current = false;
    setState(true);
    try {
      if (kind === "dropbox") {
        await apiBrowser().syncDropbox(connectorId);
      } else {
        await apiBrowser().syncSlack(connectorId);
      }
    } catch {
      finishedRef.current = true;
      setState(false);
      toast.show(copy.syncFailedToast, "error");
      return;
    }
    toast.show(copy.syncStarted, "info");
    timer.current = setTimeout(() => finish(), SYNC_SAFETY_MS);
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
