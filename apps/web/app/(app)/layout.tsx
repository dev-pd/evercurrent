import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { AppShell } from "@/components/layout/app-shell";

/**
 * Shared shell for every authed page. Living in a layout (not each page) keeps
 * the sidebar, header, and Eve rail mounted across navigation — only the page
 * content swaps, so switching tabs no longer remounts the whole app.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login");
  }
  return <AppShell>{children}</AppShell>;
}
