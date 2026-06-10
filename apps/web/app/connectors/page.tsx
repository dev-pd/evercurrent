export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { AppShell } from "@/components/layout/app-shell";
import { ConnectorButtons } from "@/components/connectors/connector-buttons";
import { DropboxConnector } from "@/components/connectors/dropbox-connector";

export default async function ConnectorsPage() {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/connectors");
  }
  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <header className="border-b border-zinc-200 pb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Connectors</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Wire EverCurrent into your team&apos;s communication and document sources.
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Slack</h2>
            <p className="text-xs text-zinc-500">
              Connect your workspace so team chatter feeds the daily digest.
            </p>
          </div>
          <ConnectorButtons />
        </section>

        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Dropbox</h2>
            <p className="text-xs text-zinc-500">
              Sync a folder of specs, BOMs, ECOs, or test reports. PDFs are
              chunked, embedded, and surfaced alongside Slack signals.
            </p>
          </div>
          <DropboxConnector />
        </section>
      </div>
    </AppShell>
  );
}
