import Link from "next/link";
import type { ReactNode } from "react";
import {
  Bell,
  CircuitBoard,
  FileText,
  GanttChartSquare,
  Home,
  ListChecks,
  Plug,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";
import { UserBadge } from "@/components/auth/user-badge";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
}

const NAV_PRIMARY: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/timeline", label: "Timeline", icon: GanttChartSquare },
  { href: "/insights", label: "Insights", icon: Sparkles },
  { href: "/decisions", label: "Decisions", icon: FileText },
  { href: "/subscriptions", label: "Subscriptions", icon: ListChecks },
];

const NAV_SECONDARY: NavItem[] = [
  { href: "/connectors", label: "Connectors", icon: Plug },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface AppShellProps {
  children: ReactNode;
  orgName?: string;
}

export function AppShell({ children, orgName }: AppShellProps) {
  const workspace = orgName ?? "Atlas Hardware";
  return (
    <div className="flex min-h-screen bg-[var(--surface-bg)]">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-[var(--border-default)] bg-white sm:flex">
        <div className="flex items-center gap-2 border-b border-[var(--border-default)] px-4 py-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
            <CircuitBoard className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-semibold tracking-tight">
              EverCurrent
            </span>
            <span className="truncate text-[11px] text-[var(--text-muted)]">
              {workspace}
            </span>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-6 px-2 py-4">
          <NavGroup items={NAV_PRIMARY} />
          <div className="flex flex-col gap-1">
            <NavLabel>Workspace</NavLabel>
            <NavGroup items={NAV_SECONDARY} />
          </div>
        </nav>

        <div className="border-t border-[var(--border-default)] px-4 py-3 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
          <span className="font-mono">v0.12.0</span> · phase 12
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-[var(--border-default)] bg-white px-4 py-2.5 sm:px-6">
          <div className="text-xs text-[var(--text-muted)] sm:hidden">EverCurrent</div>
          <button
            type="button"
            aria-label="Search"
            className="hidden items-center gap-2 rounded-md border border-[var(--border-default)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] sm:flex"
          >
            <Search className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Search messages, decisions, docs</span>
            <kbd className="ml-2 rounded border border-[var(--border-default)] bg-white px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-muted)]">
              ⌘K
            </kbd>
          </button>

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              aria-label="Notifications"
              className="relative rounded-md p-1.5 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
              <span className="absolute right-1 top-1 inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-accent-500)]" />
            </button>
            <UserBadge />
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-8 sm:py-8">{children}</main>
      </div>
    </div>
  );
}

function NavGroup({ items }: { items: NavItem[] }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              className="group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              <Icon
                className="h-4 w-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)]"
                aria-hidden="true"
              />
              <span>{item.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function NavLabel({ children }: { children: ReactNode }) {
  return (
    <span className="px-2 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
      {children}
    </span>
  );
}
