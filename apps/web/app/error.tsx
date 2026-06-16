"use client";

import { useEffect } from "react";
import Link from "next/link";
import { TriangleAlert, RotateCw, ArrowLeft } from "lucide-react";
import { messages } from "@/lib/messages";

const copy = messages.errors;

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error("route error", error);
    }
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[var(--surface-bg)] px-4 text-center">
      <div className="flex max-w-md flex-col items-center gap-5">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-red-50 text-red-600">
          <TriangleAlert className="h-6 w-6" aria-hidden="true" />
        </span>

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
            {copy.title}
          </h1>
          <p className="mt-2 text-sm text-[var(--text-muted)]">{copy.routeBody}</p>
          {error.digest && (
            <p className="mt-2 font-mono text-[11px] text-[var(--text-muted)]">
              {copy.refPrefix} {error.digest}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--color-accent-600)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-accent-700)]"
          >
            <RotateCw className="h-4 w-4" aria-hidden="true" />
            {messages.common.tryAgain}
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-md border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            {copy.backToDigest}
          </Link>
        </div>
      </div>
    </main>
  );
}
