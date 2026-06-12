// Skeleton shown while the digest's server fetches resolve. No async work here
// (it's a Suspense fallback) — just shimmer placeholders matching the layout.
function Shimmer({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-[var(--surface-muted)] ${className}`} />;
}

export default function DashboardLoading() {
  return (
    <div className="flex min-h-screen bg-[var(--surface-bg)]">
      <aside className="hidden w-56 shrink-0 border-r border-[var(--border-default)] bg-white sm:block" />
      <div className="min-w-0 flex-1 px-4 py-5 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-4">
          {/* context bar */}
          <div className="rounded-xl border border-[var(--border-default)] bg-white px-5 py-4">
            <div className="flex items-center gap-3">
              <Shimmer className="h-9 w-9 rounded-md" />
              <div className="flex-1 space-y-2">
                <Shimmer className="h-3 w-40" />
                <Shimmer className="h-2.5 w-56" />
              </div>
            </div>
            <Shimmer className="mt-3 h-3 w-48" />
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Shimmer key={i} className="h-12" />
              ))}
            </div>
          </div>

          {/* 3 columns */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, col) => (
              <div
                key={col}
                className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-muted)] p-3"
              >
                <Shimmer className="mb-3 h-4 w-28 bg-[var(--border-default)]" />
                <div className="space-y-2.5">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Shimmer key={i} className="h-20 bg-white" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
