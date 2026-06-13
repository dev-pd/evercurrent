import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  toolbar?: ReactNode;
}

export function PageHeader({ title, subtitle, action, toolbar }: PageHeaderProps) {
  return (
    <div className="sticky top-0 z-20 -mt-5 border-b border-[var(--glass-border)] bg-white/55 pt-5 backdrop-blur-xl">
      <div className={`flex items-end justify-between gap-3 ${toolbar ? "pb-3" : "pb-4"}`}>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-[var(--text-muted)]">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {toolbar && <div className="pb-3">{toolbar}</div>}
    </div>
  );
}

export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">{children}</div>;
}
