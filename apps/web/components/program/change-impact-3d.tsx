"use client";

import dynamic from "next/dynamic";

const Subsystem3D = dynamic(() => import("./subsystem-3d"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center text-xs text-[var(--text-muted)]">
      Rendering 3D…
    </div>
  ),
});

export function ChangeImpact3D({ highlighted }: { highlighted: string[] }) {
  return (
    <div className="glass rounded-xl border border-[var(--glass-border)] p-1">
      <div className="px-4 pt-3 pb-1">
        <h3 className="text-xs font-semibold tracking-wider text-[var(--text-secondary)] uppercase">
          Change impact
        </h3>
        <p className="text-[11px] text-[var(--text-muted)]">
          The Atlas v2 robot — the part Eve flagged glows. Drag to rotate.
        </p>
      </div>
      <div className="h-80">
        <Subsystem3D highlighted={highlighted} />
      </div>
    </div>
  );
}
