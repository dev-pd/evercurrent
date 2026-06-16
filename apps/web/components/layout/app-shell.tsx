import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { CircuitBoard, FileText, GanttChartSquare, Home, Settings, Sparkles } from "lucide-react";
import { UserBadge } from "@/components/auth/user-badge";
import { ViewAsSwitcher } from "@/components/layout/view-as-switcher";
import { DecisionModal } from "@/components/decisions/decision-modal";
import { messages } from "@/lib/messages";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: messages.nav.digest, icon: Home },
  { href: "/decisions", label: messages.nav.decisions, icon: FileText },
  { href: "/insights", label: messages.nav.insights, icon: Sparkles },
  { href: "/timeline", label: messages.nav.timeline, icon: GanttChartSquare },
  { href: "/settings", label: messages.nav.settings, icon: Settings },
];

interface AppShellProps {
  children: ReactNode;
  orgName: string;
  phase?: string;
  day?: number;
  accent?: string;
  monogram?: string;
  isAdmin?: boolean;
  eveRail?: boolean;
}

export function AppShell({
  children,
  orgName,
  phase,
  day,
  accent,
  monogram,
  isAdmin = false,
  eveRail = true,
}: AppShellProps) {
  const workspace = orgName || messages.common.workspaceFallback;
  const phaseLabel = phase ? `${phase.toUpperCase()}${day != null ? ` · Day ${day}` : ""}` : null;
  const themeStyle = accent
    ? ({ "--color-accent-600": accent, "--color-accent-700": accent } as CSSProperties)
    : undefined;
  return (
    <div className="flex h-screen overflow-hidden" style={themeStyle}>
      <aside className="glass glass-sheen hidden w-56 shrink-0 flex-col border-r border-[var(--glass-border)] sm:flex">
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border-default)] px-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-sm font-bold text-white">
            {monogram ? (
              monogram.charAt(0).toUpperCase()
            ) : (
              <CircuitBoard className="h-4 w-4" aria-hidden="true" />
            )}
          </span>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-semibold tracking-tight">
              {messages.common.brand}
            </span>
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
        <header className="glass flex h-14 shrink-0 items-center gap-2 border-b border-[var(--glass-border)] px-4 sm:px-6">
          <span className="text-sm font-semibold text-[var(--text-primary)]">{workspace}</span>
          {phaseLabel && (
            <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-[var(--text-muted)] uppercase">
              {phaseLabel}
            </span>
          )}
          <div className="ml-auto">{isAdmin && <ViewAsSwitcher />}</div>
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
      <DecisionModal />
    </div>
  );
}
