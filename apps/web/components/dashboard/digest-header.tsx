import { RegenerateButton } from "@/components/dashboard/regenerate-button";

interface DigestHeaderProps {
  projectName: string;
  phase: string;
  dayIndex: number;
  generatedAt: string | null;
}

function formatGeneratedAt(generatedAt: string | null): string {
  if (!generatedAt) return "not yet generated";
  try {
    return new Date(generatedAt).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return generatedAt;
  }
}

export function DigestHeader({ projectName, phase, dayIndex, generatedAt }: DigestHeaderProps) {
  return (
    <header className="flex flex-col gap-3 border-b border-[var(--border-default)] pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          <span>Daily digest</span>
          <span aria-hidden="true">·</span>
          <span className="font-mono">{formatGeneratedAt(generatedAt)}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
          {projectName}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-[var(--color-accent-200)] bg-[var(--color-accent-50)] px-2 py-0.5 font-medium text-[var(--color-accent-700)]">
            phase {phase}
          </span>
          <span className="rounded-full border border-[var(--border-default)] bg-white px-2 py-0.5 font-mono text-[var(--text-secondary)]">
            day {dayIndex}
          </span>
        </div>
      </div>
      <RegenerateButton />
    </header>
  );
}
