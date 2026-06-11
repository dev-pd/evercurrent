import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

/** One consistent page header (title size, subtitle, spacing) across all pages. */
export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex items-end justify-between gap-3 border-b border-[var(--border-default)] pb-4">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-[var(--text-muted)]">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/** Standard content container — same max width + spacing on every page. */
export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">{children}</div>;
}
