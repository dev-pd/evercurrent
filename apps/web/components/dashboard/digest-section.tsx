import { DigestItemCard } from "@/components/dashboard/digest-item-card";
import type { DigestItemV2 } from "@/lib/types";

type Bucket = DigestItemV2["bucket"];

interface DigestSectionProps {
  bucket: Bucket;
  items: DigestItemV2[];
}

const BUCKET_META: Record<
  Bucket,
  { label: string; dotClass: string; ringClass: string; description: string }
> = {
  top_priority: {
    label: "Top priority",
    dotClass: "bg-red-500",
    ringClass: "ring-red-100",
    description: "Action expected today",
  },
  watch_outs: {
    label: "Watch-outs",
    dotClass: "bg-amber-500",
    ringClass: "ring-amber-100",
    description: "Likely to need attention soon",
  },
  fyi: {
    label: "FYI",
    dotClass: "bg-sky-500",
    ringClass: "ring-sky-100",
    description: "Context only — no action needed",
  },
};

export function DigestSection({ bucket, items }: DigestSectionProps) {
  if (items.length === 0) return null;
  const meta = BUCKET_META[bucket];

  return (
    <section className="flex flex-col gap-3" aria-label={meta.label}>
      <header className="flex items-baseline justify-between border-b border-[var(--border-default)] pb-2">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ring-4 ${meta.dotClass} ${meta.ringClass}`}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            {meta.label}
          </h2>
          <span className="font-mono text-xs text-[var(--text-muted)] tabular-nums">
            {items.length}
          </span>
        </div>
        <span className="hidden text-[11px] text-[var(--text-muted)] sm:inline">
          {meta.description}
        </span>
      </header>
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <DigestItemCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}
