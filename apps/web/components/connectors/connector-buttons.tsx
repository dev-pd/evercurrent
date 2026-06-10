"use client";

import { useState } from "react";
import { Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

async function startSlackInstall(): Promise<void> {
  const response = await fetch("/api/proxy/connectors/slack/install", {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`install failed: ${response.status}`);
  }
  const body = (await response.json()) as { redirect_url?: string };
  if (body.redirect_url) {
    window.location.href = body.redirect_url;
  }
}

export function ConnectorButtons() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    setPending(true);
    setError(null);
    try {
      await startSlackInstall();
    } catch (e) {
      setError(e instanceof Error ? e.message : "install failed");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-900">
            <Plug className="h-4 w-4" aria-hidden="true" />
            Connect Slack
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            Pipe messages from your team channels into the daily digest.
          </p>
        </div>
        <Button onClick={onClick} disabled={pending} size="sm">
          {pending ? <Spinner size="xs" /> : "Install"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
