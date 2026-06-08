import { DigestItemCard } from "@/components/dashboard/digest-item-card";
import { cn } from "@/lib/utils";
import type { DigestItemV2 } from "@/lib/types";

type Bucket = DigestItemV2["bucket"];

interface DigestSectionProps {
  bucket: Bucket;
  items: DigestItemV2[];
}

const BUCKET_META: Record<Bucket, { label: string; accent: string; dot: string }> = {
  top_priority: {
    label: "Top priority",
    accent: "border-l-4 border-red-500",
    dot: "bg-red-500",
  },
  watch_outs: {
    label: "Watch-outs",
    accent: "border-l-4 border-amber-500",
    dot: "bg-amber-500",
  },
  fyi: {
    label: "FYI",
    accent: "border-l-4 border-sky-500",
    dot: "bg-sky-500",
  },
};

export function DigestSection({ bucket, items }: DigestSectionProps) {
  if (items.length === 0) return null;
  const meta = BUCKET_META[bucket];

  return (
    <section className={cn("pl-3", meta.accent)} aria-label={meta.label}>
      <header className="mb-3 flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", meta.dot)} aria-hidden="true" />
        <h2 className="text-sm font-semibold tracking-wide text-zinc-700 uppercase">
          {meta.label}
        </h2>
        <span className="text-xs text-zinc-500">({items.length})</span>
      </header>
      <div className="flex flex-col gap-3">
        {items.map((item) => (
          <DigestItemCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}
