import { CardSourceList } from "@/components/cards/card-source-list";
import { CardEdgesList } from "@/components/cards/card-edges-list";
import { formatTimestamp } from "@/lib/format-date";
import type { CardResponse } from "@/lib/types";

interface KnowledgeCardProps {
  card: CardResponse;
}

export function KnowledgeCard({ card }: KnowledgeCardProps) {
  const decided = formatTimestamp(card.decided_at);
  const updated = formatTimestamp(card.updated_at);

  return (
    <article className="glass-strong flex flex-col gap-6 rounded-lg border border-[var(--glass-border)] p-6">
      <header className="flex flex-col gap-2 border-b border-zinc-200 pb-4">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">
            {card.kind}
          </span>
          <span>status: {card.status}</span>
          {typeof card.confidence === "number" && (
            <span>confidence: {card.confidence.toFixed(2)}</span>
          )}
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-900">{card.summary}</h1>
        <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
          {decided && <span>decided: {decided}</span>}
          {updated && <span>updated: {updated}</span>}
        </div>
      </header>

      {card.body && (
        <section>
          <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
            Detail
          </h2>
          <p className="text-sm whitespace-pre-line text-zinc-800">{card.body}</p>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
          Sources
        </h2>
        <CardSourceList sources={card.sources} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">Impact</h2>
        <CardEdgesList edges={card.edges} />
      </section>

      {card.activity.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
            Activity
          </h2>
          <ul className="flex flex-col gap-1.5 text-sm">
            {card.activity.map((activity) => {
              const at = formatTimestamp(activity.at);
              return (
                <li key={activity.id} className="text-zinc-700">
                  <span className="text-xs text-zinc-500">{at}</span>
                  {activity.actor && <span className="ml-2 font-medium">{activity.actor}</span>}
                  <span className="ml-2">{activity.description}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </article>
  );
}
