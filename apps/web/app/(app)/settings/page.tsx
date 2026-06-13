export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { AppShell } from "@/components/layout/app-shell";
import { PageContainer, PageHeader } from "@/components/layout/page-header";

export default async function SettingsPage() {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/settings");
  }
  const user = session.user;
  const displayName = user.name ?? user.email ?? "Account";
  return (
    <AppShell>
      <PageContainer>
        <PageHeader
          title="Settings"
          subtitle="Account, workspace, sources, and notification preferences."
        />

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Account</h2>
          <div className="flex items-center justify-between rounded-lg border border-[var(--border-default)] bg-white p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-accent-100)] text-sm font-semibold text-[var(--color-accent-700)]">
                {displayName.charAt(0).toUpperCase()}
              </span>
              <div className="flex flex-col">
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {displayName}
                </span>
                {user.email && (
                  <span className="text-xs text-[var(--text-muted)]">{user.email}</span>
                )}
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

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Workspace</h2>
          <div className="rounded-lg border border-[var(--border-default)] bg-white p-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  Atlas Hardware
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  Single-workspace mode
                </span>
              </div>
              <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                active
              </span>
            </div>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Notifications</h2>
          <div className="rounded-lg border border-[var(--border-default)] bg-white p-4 text-sm text-[var(--text-muted)]">
            Daily digest delivery (email + Slack DM) is on the roadmap.
          </div>
        </section>
      </PageContainer>
    </AppShell>
  );
}
