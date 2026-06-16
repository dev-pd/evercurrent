import { messages } from "@/lib/messages";
import type { DigestItemV2 } from "@/lib/types";
import type { DigestBullet, ParsedDigest } from "@/lib/digest-parse";

const copy = messages.digest;

type Bucket = DigestItemV2["bucket"];

const BUCKET_META: Record<
  Bucket,
  { label: string; dot: string; ring: string; accent: string; desc: string }
> = {
  top_priority: {
    label: copy.topPriorityLabel,
    dot: "bg-red-500",
    ring: "ring-red-100",
    accent: "border-l-red-500",
    desc: copy.topPriorityDesc,
  },
  watch_outs: {
    label: copy.watchOutsLabel,
    dot: "bg-amber-500",
    ring: "ring-amber-100",
    accent: "border-l-amber-500",
    desc: copy.watchOutsDesc,
  },
  fyi: {
    label: copy.fyiLabel,
    dot: "bg-sky-500",
    ring: "ring-sky-100",
    accent: "border-l-sky-500",
    desc: copy.fyiDesc,
  },
};

const ORDER: Bucket[] = ["top_priority", "watch_outs", "fyi"];

function BulletCard({ bullet, accent }: { bullet: DigestBullet; accent: string }) {
  return (
    <article
      className={`rounded-lg border border-l-2 border-[var(--glass-border)] ${accent} glass-strong px-4 py-3 transition-shadow hover:shadow`}
    >
      <p className="text-sm leading-relaxed text-[var(--text-primary)]">{bullet.text}</p>
    </article>
  );
}

function DigestColumn({ bucket, bullets }: { bucket: Bucket; bullets: DigestBullet[] }) {
  const meta = BUCKET_META[bucket];
  return (
    <section
      className="glass flex min-h-0 min-w-0 flex-col rounded-xl border border-[var(--glass-border)]"
      aria-label={meta.label}
    >
      <header className="flex shrink-0 items-center justify-between border-b border-[var(--border-default)] px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ring-4 ${meta.dot} ${meta.ring}`}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</h2>
          <span className="font-mono text-xs text-[var(--text-muted)] tabular-nums">
            {bullets.length}
          </span>
        </div>
        <span className="hidden text-[11px] text-[var(--text-muted)] sm:inline">{meta.desc}</span>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {bullets.length === 0 ? (
          <p className="rounded-lg border border-dashed border-[var(--border-default)] px-3 py-8 text-center text-xs text-[var(--text-muted)]">
            {copy.empty}
          </p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {bullets.map((bullet, i) => (
              <BulletCard key={i} bullet={bullet} accent={meta.accent} />
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
