import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  toolbar?: ReactNode;
}

export function PageHeader({ title, subtitle, action, toolbar }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">
            {title}
          </h1>
          {subtitle && <p className="mt-1 text-sm text-[var(--text-muted)]">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {toolbar && <div>{toolbar}</div>}
    </div>
  );
}

export function PageContainer({ header, children }: { header?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      {header && (
        <div className="shrink-0 border-b border-[var(--border-default)] px-4 py-4 sm:px-6">
          <div className="mx-auto w-full max-w-5xl">{header}</div>
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">{children}</div>
      </div>
    </div>
  );
}
