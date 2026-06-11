import { DigestItemCard } from "@/components/dashboard/digest-item-card";
import type { DigestItemV2 } from "@/lib/types";

type Bucket = DigestItemV2["bucket"];

const BUCKET_META: Record<Bucket, { label: string; dotClass: string; ringClass: string }> = {
  top_priority: { label: "Top priority", dotClass: "bg-red-500", ringClass: "ring-red-100" },
  watch_outs: { label: "Watch-outs", dotClass: "bg-amber-500", ringClass: "ring-amber-100" },
  fyi: { label: "FYI", dotClass: "bg-sky-500", ringClass: "ring-sky-100" },
};

const ORDER: Bucket[] = ["top_priority", "watch_outs", "fyi"];

function DigestColumn({ bucket, items }: { bucket: Bucket; items: DigestItemV2[] }) {
  const meta = BUCKET_META[bucket];
  return (
    <section className="flex min-w-0 flex-col gap-3" aria-label={meta.label}>
      <header className="flex items-center gap-2 border-b border-[var(--border-default)] pb-2">
        <span
          className={`h-2 w-2 rounded-full ring-4 ${meta.dotClass} ${meta.ringClass}`}
          aria-hidden="true"
        />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</h2>
        <span className="font-mono text-xs tabular-nums text-[var(--text-muted)]">
          {items.length}
        </span>
      </header>
      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-[var(--border-default)] px-3 py-6 text-center text-xs text-[var(--text-muted)]">
          Nothing here.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((item) => (
            <DigestItemCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

interface DigestColumnsProps {
  buckets: Record<Bucket, DigestItemV2[]>;
}

export function DigestColumns({ buckets }: DigestColumnsProps) {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      {ORDER.map((bucket) => (
        <DigestColumn key={bucket} bucket={bucket} items={buckets[bucket]} />
      ))}
    </div>
  );
}
