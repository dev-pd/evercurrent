import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--surface-bg)]">
      <Loader2 className="h-6 w-6 animate-spin text-[var(--color-accent-600)]" aria-label="Loading" />
    </main>
  );
}
