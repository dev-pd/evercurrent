import Link from "next/link";
import type { ReactNode } from "react";
import { Bell, FileText, Home, Plug, Settings, ListChecks } from "lucide-react";
import { UserBadge } from "@/components/auth/user-badge";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/decisions", label: "Decisions", icon: FileText },
  { href: "/connectors", label: "Connectors", icon: Plug },
  { href: "/subscriptions", label: "Subscriptions", icon: ListChecks },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface AppShellProps {
  children: ReactNode;
  orgName?: string;
}

export function AppShell({ children, orgName }: AppShellProps) {
  return (
    <div className="flex min-h-screen bg-zinc-50">
      <aside className="hidden w-56 flex-col border-r border-zinc-200 bg-white sm:flex">
        <div className="px-4 py-5">
          <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
            EverCurrent
          </Link>
          {orgName && <div className="mt-1 text-xs text-zinc-500">{orgName}</div>}
        </div>
        <nav className="flex flex-col gap-0.5 px-2 py-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-zinc-700 hover:bg-zinc-100"
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3">
          <div className="text-sm text-zinc-500 sm:hidden">EverCurrent</div>
          <div className="ml-auto flex items-center gap-3">
            <button
              type="button"
              aria-label="Notifications"
              className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
            </button>
            <UserBadge />
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-8">{children}</main>
      </div>
    </div>
  );
}
