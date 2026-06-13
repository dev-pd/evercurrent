// Shared loading skeleton for every authed page. Renders inside the persistent
// shell (the layout's <main>), so navigating never tears down the sidebar,
// header, or Eve rail — only this content area shimmers until the page resolves.
function Shimmer({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-[var(--surface-muted)] ${className}`} />;
}

export default function AppLoading() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
      <div className="flex items-end justify-between gap-3 border-b border-[var(--border-default)] pb-4">
        <div className="space-y-2">
          <Shimmer className="h-5 w-40" />
          <Shimmer className="h-3 w-64" />
        </div>
        <Shimmer className="h-8 w-24" />
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Shimmer key={i} className="h-20 w-full" />
        ))}
      </div>
    </div>
  );
}
