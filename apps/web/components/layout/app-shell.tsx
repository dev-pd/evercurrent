import Link from "next/link";
import type { ReactNode } from "react";
import { CircuitBoard, FileText, GanttChartSquare, Home, Settings, Sparkles } from "lucide-react";
import { UserBadge } from "@/components/auth/user-badge";
import { ViewAsSwitcher } from "@/components/layout/view-as-switcher";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Digest", icon: Home },
  { href: "/decisions", label: "Decisions", icon: FileText },
  { href: "/insights", label: "Insights", icon: Sparkles },
  { href: "/timeline", label: "Timeline", icon: GanttChartSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface AppShellProps {
  children: ReactNode;
  orgName?: string;
  /** Pages own their scroll, so the shell stays fixed-height. */
  eveRail?: boolean;
}

export function AppShell({ children, orgName, eveRail = true }: AppShellProps) {
  const workspace = orgName ?? "Atlas Hardware";
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--surface-bg)]">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-[var(--border-default)] bg-white sm:flex">
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border-default)] px-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
            <CircuitBoard className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-semibold tracking-tight">EverCurrent</span>
            <span className="truncate text-[11px] text-[var(--text-muted)]">{workspace}</span>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-4">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon
                  className="h-4 w-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)]"
                  aria-hidden="true"
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <UserBadge />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border-default)] bg-white px-4 sm:px-6">
          <span className="text-sm font-semibold text-[var(--text-primary)]">{workspace}</span>
          <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-[var(--text-muted)] uppercase">
            DVT · Day 42
          </span>
          <div className="ml-auto">
            <ViewAsSwitcher />
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
