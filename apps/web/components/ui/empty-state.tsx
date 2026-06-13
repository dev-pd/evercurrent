interface EmptyStateProps {
  title: string;
  hint?: string;
}

export function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="glass rounded-lg border border-dashed border-[var(--glass-border)] p-8 text-center">
      <p className="text-sm font-medium text-[var(--text-primary)]">{title}</p>
      {hint && <p className="mt-1 text-xs text-[var(--text-muted)]">{hint}</p>}
    </div>
  );
}
