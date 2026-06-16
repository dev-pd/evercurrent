import Link from "next/link";
import { CircuitBoard, ArrowLeft } from "lucide-react";
import { messages } from "@/lib/messages";

const copy = messages.errors;

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[var(--surface-bg)] px-4 text-center">
      <div className="flex flex-col items-center gap-5">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-accent-600)] text-white">
          <CircuitBoard className="h-6 w-6" aria-hidden="true" />
        </span>

        <div>
          <p className="font-mono text-sm font-semibold tracking-widest text-[var(--color-accent-600)] uppercase">
            {copy.notFoundCode}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
            {copy.notFoundTitle}
          </h1>
          <p className="mt-2 max-w-sm text-sm text-[var(--text-muted)]">{copy.notFoundBody}</p>
        </div>

        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-accent-700)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {copy.notFoundBack}
        </Link>
      </div>
    </main>
  );
}
