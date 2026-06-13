export const dynamic = "force-dynamic";

import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { SourcesCard } from "@/components/settings/sources-card";
import { TeamCard } from "@/components/settings/team-card";
import type { ConnectorSummary, Me, MemberSummary } from "@/lib/types";

async function safe<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

export default async function SettingsPage() {
  const session = await auth0.getSession();
  const user = session?.user;
  const client = await apiServer();

  const me = await safe<Me>(() => client.getMe());
  const isAdmin = me?.role === "admin";

  const [members, connectors] = isAdmin
    ? await Promise.all([
        safe<MemberSummary[]>(() => client.listMembers()),
        safe<ConnectorSummary[]>(() => client.listConnectors()),
      ])
    : [null, null];

  const displayName = me?.display_name ?? user?.name ?? user?.email ?? "Account";
  const email = me?.email ?? user?.email ?? null;

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        subtitle={
          isAdmin
            ? "Account, sources, and team — the admin control panel."
            : "Your account and preferences."
        }
      />

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Account</h2>
        <div className="flex items-center justify-between rounded-lg border border-[var(--border-default)] bg-white p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-accent-100)] text-sm font-semibold text-[var(--color-accent-700)]">
              {displayName.charAt(0).toUpperCase()}
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-[var(--text-primary)]">{displayName}</span>
              <span className="text-xs text-[var(--text-muted)]">
                {me?.org_name || "Workspace"}
                {email ? ` · ${email}` : ""}
                {isAdmin ? " · Admin" : ""}
              </span>
            </div>
          </div>
          <a
            href="/api/auth/logout"
            className="inline-flex items-center rounded-md border border-[var(--border-default)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
          >
            Log out
          </a>
        </div>
      </section>

      {isAdmin ? (
        <>
          <SourcesCard connectors={connectors ?? []} />
          <TeamCard members={members ?? []} />
        </>
      ) : (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Workspace</h2>
          <div className="rounded-lg border border-[var(--border-default)] bg-white p-4 text-sm text-[var(--text-muted)]">
            Sources and team setup are managed by your workspace admin.
          </div>
        </section>
      )}
    </PageContainer>
  );
}
