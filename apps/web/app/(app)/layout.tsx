import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";

async function safe<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login");
  }

  const client = await apiServer();
  const [me, projects] = await Promise.all([
    safe(() => client.getMe()),
    safe(() => client.listProjects()),
  ]);
  const project = projects?.[0];

  return (
    <AppShell orgName={me?.org_name ?? ""} phase={project?.current_phase} day={project?.current_day}>
      {children}
    </AppShell>
  );
}
