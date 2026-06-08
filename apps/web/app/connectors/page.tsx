import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { AppShell } from "@/components/layout/app-shell";
import { ConnectorButtons } from "@/components/connectors/connector-buttons";

export default async function ConnectorsPage() {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/connectors");
  }
  return (
    <AppShell>
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <header className="border-b border-zinc-200 pb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Connectors</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Wire EverCurrent into your team&apos;s Slack and Google Drive.
          </p>
        </header>
        <ConnectorButtons />
      </div>
    </AppShell>
  );
}
