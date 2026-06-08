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
    return new Date(generatedAt).toLocaleString();
  } catch {
    return generatedAt;
  }
}

export function DigestHeader({ projectName, phase, dayIndex, generatedAt }: DigestHeaderProps) {
  return (
    <header className="flex flex-col gap-2 border-b border-zinc-200 pb-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{projectName}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-500">
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">
            {phase}
          </span>
          <span>day {dayIndex}</span>
          <span>last digest: {formatGeneratedAt(generatedAt)}</span>
        </div>
      </div>
      <RegenerateButton />
    </header>
  );
}
