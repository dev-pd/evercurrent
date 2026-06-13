import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  /** Optional second row (e.g. filter chips) that pins together with the header. */
  toolbar?: ReactNode;
}

/**
 * One consistent page header across pages. Sticky to the top of the scrolling
 * <main>: the negative top margin + matching padding let the opaque background
 * bleed over the container's top gap so scrolled content never peeks above it.
 * The optional toolbar row lives inside the same sticky block, so page filters
 * stay pinned alongside the title.
 */
export function PageHeader({ title, subtitle, action, toolbar }: PageHeaderProps) {
  return (
    <div className="sticky top-0 z-20 -mt-5 border-b border-[var(--border-default)] bg-[var(--surface-bg)] pt-5">
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

/** Standard content container — same max width + spacing on every page. */
export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">{children}</div>;
}
