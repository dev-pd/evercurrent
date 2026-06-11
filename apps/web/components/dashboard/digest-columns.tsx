import type { DigestItemV2 } from "@/lib/types";
import type { DigestBullet, ParsedDigest } from "@/lib/digest-parse";

type Bucket = DigestItemV2["bucket"];

const BUCKET_META: Record<
  Bucket,
  { label: string; dot: string; ring: string; accent: string; desc: string }
> = {
  top_priority: {
    label: "Top priority",
    dot: "bg-red-500",
    ring: "ring-red-100",
    accent: "border-l-red-500",
    desc: "Act today",
  },
  watch_outs: {
    label: "Watch-outs",
    dot: "bg-amber-500",
    ring: "ring-amber-100",
    accent: "border-l-amber-500",
    desc: "Keep an eye on",
  },
  fyi: {
    label: "FYI",
    dot: "bg-sky-500",
    ring: "ring-sky-100",
    accent: "border-l-sky-500",
    desc: "Context only",
  },
};

const ORDER: Bucket[] = ["top_priority", "watch_outs", "fyi"];

function BulletCard({ bullet, accent }: { bullet: DigestBullet; accent: string }) {
  return (
    <article
      className={`rounded-lg border border-[var(--border-default)] border-l-2 ${accent} bg-white px-4 py-3 shadow-sm transition-shadow hover:shadow`}
    >
      <p className="text-sm leading-relaxed text-[var(--text-primary)]">{bullet.text}</p>
    </article>
  );
}

function DigestColumn({ bucket, bullets }: { bucket: Bucket; bullets: DigestBullet[] }) {
  const meta = BUCKET_META[bucket];
  return (
    <section
      className="flex min-h-0 min-w-0 flex-col rounded-xl border border-[var(--border-default)] bg-[var(--surface-muted)]"
      aria-label={meta.label}
    >
      <header className="flex shrink-0 items-center justify-between border-b border-[var(--border-default)] px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ring-4 ${meta.dot} ${meta.ring}`}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</h2>
          <span className="font-mono text-xs tabular-nums text-[var(--text-muted)]">
            {bullets.length}
          </span>
        </div>
        <span className="hidden text-[11px] text-[var(--text-muted)] sm:inline">{meta.desc}</span>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {bullets.length === 0 ? (
          <p className="rounded-lg border border-dashed border-[var(--border-default)] px-3 py-8 text-center text-xs text-[var(--text-muted)]">
            Nothing here.
          </p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {bullets.map((b, i) => (
              <BulletCard key={i} bullet={b} accent={meta.accent} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export function DigestColumns({ buckets }: { buckets: ParsedDigest }) {
  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto md:grid-cols-2 md:overflow-visible lg:grid-cols-3">
      {ORDER.map((bucket) => (
        <DigestColumn key={bucket} bucket={bucket} bullets={buckets[bucket]} />
      ))}
    </div>
  );
}
