"use client";

import { useCallback, useEffect, useState } from "react";
import { Folder, FolderOpen, Plug, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

interface ConnectorSummary {
  id: string;
  kind: string;
  status: string;
}

interface DropboxFolder {
  id: string;
  name: string;
  path: string;
}

interface SyncResult {
  total_pdfs: number;
  ingested: number;
  skipped: number;
  failed: number;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body.slice(0, 200)}`);
  }
  return (await response.json()) as T;
}

async function startInstall(): Promise<string> {
  const body = await fetchJson<{ redirect_url?: string }>(
    "/api/proxy/connectors/dropbox/install",
    { method: "POST" },
  );
  if (!body.redirect_url) {
    throw new Error("missing redirect_url");
  }
  return body.redirect_url;
}

export function DropboxConnector() {
  const [connector, setConnector] = useState<ConnectorSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [folders, setFolders] = useState<DropboxFolder[] | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<DropboxFolder | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadConnector = useCallback(async () => {
    try {
      const list = await fetchJson<ConnectorSummary[]>("/api/proxy/connectors");
      const dropbox = list.find((c) => c.kind === "dropbox") ?? null;
      setConnector(dropbox);
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConnector();
  }, [loadConnector]);

  const loadFolders = useCallback(async (id: string) => {
    setError(null);
    try {
      const list = await fetchJson<DropboxFolder[]>(
        `/api/proxy/connectors/${id}/dropbox/folders`,
      );
      setFolders(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "folder list failed");
    }
  }, []);

  useEffect(() => {
    if (connector) {
      void loadFolders(connector.id);
    }
  }, [connector, loadFolders]);

  const onInstall = async () => {
    setInstalling(true);
    setError(null);
    try {
      const url = await startInstall();
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "install failed");
      setInstalling(false);
    }
  };

  const onSync = async (folder: DropboxFolder) => {
    if (!connector) return;
    setSyncing(true);
    setSyncResult(null);
    setError(null);
    setSelectedFolder(folder);
    try {
      const result = await fetchJson<SyncResult>(
        `/api/proxy/connectors/${connector.id}/dropbox/sync`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_path: folder.path, folder_name: folder.name }),
        },
      );
      setSyncResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "sync failed");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <Spinner size="sm" label="Loading Dropbox connector…" />
      </div>
    );
  }

  if (!connector) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-900">
            <Plug className="h-4 w-4" aria-hidden="true" />
            Connect Dropbox
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            Authorize Dropbox to sync PDFs (specs, ECOs, FAI reports) into the
            knowledge graph.
          </p>
          {error && (
            <p role="alert" className="mt-2 text-xs text-red-600">
              {error}
            </p>
          )}
        </div>
        <Button onClick={onInstall} disabled={installing} size="sm">
          {installing ? <Spinner size="xs" /> : "Install"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-900">
            <FolderOpen className="h-4 w-4" aria-hidden="true" />
            Dropbox connected
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            Pick a folder to sync. PDFs are chunked, embedded, and indexed for
            retrieval.
          </p>
        </div>
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-700">
          {connector.status}
        </span>
      </div>

      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}

      {folders === null ? (
        <div className="text-xs text-zinc-500">Loading folders…</div>
      ) : folders.length === 0 ? (
        <div className="text-xs text-zinc-500">
          No folders found at the root of your Dropbox.
        </div>
      ) : (
        <ul className="flex flex-col gap-1">
          {folders.map((folder) => (
            <li
              key={folder.id || folder.path}
              className="flex items-center justify-between rounded-md border border-zinc-100 px-3 py-2 hover:border-zinc-200"
            >
              <div className="flex items-center gap-2 text-sm text-zinc-900">
                <Folder className="h-4 w-4 text-zinc-400" aria-hidden="true" />
                <span>{folder.name}</span>
                <span className="font-mono text-[10px] text-zinc-400">
                  {folder.path}
                </span>
              </div>
              <Button
                onClick={() => onSync(folder)}
                disabled={syncing && selectedFolder?.path === folder.path}
                size="sm"
                variant="outline"
              >
                {syncing && selectedFolder?.path === folder.path ? (
                  <Spinner size="xs" />
                ) : (
                  <>
                    <RefreshCw className="mr-1 h-3 w-3" aria-hidden="true" />
                    Sync
                  </>
                )}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {syncResult && selectedFolder && (
        <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
          <div className="font-medium text-zinc-900">
            Synced {selectedFolder.name}
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-4">
            <Stat label="PDFs" value={syncResult.total_pdfs} />
            <Stat label="Ingested" value={syncResult.ingested} />
            <Stat label="Skipped" value={syncResult.skipped} />
            <Stat label="Failed" value={syncResult.failed} />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <div className="font-mono text-sm text-zinc-900">{value}</div>
    </div>
  );
}
