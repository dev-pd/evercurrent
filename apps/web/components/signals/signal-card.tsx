import { SignalSourceList } from "@/components/signals/signal-source-list";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import type { SignalResponse } from "@/lib/types";

const copy = messages.signal;

interface SignalCardProps {
  signal: SignalResponse;
}

export function SignalCard({ signal }: SignalCardProps) {
  const decided = formatTimestamp(signal.decided_at);
  const updated = formatTimestamp(signal.updated_at);

  return (
    <article className="glass-strong flex flex-col gap-6 rounded-lg border border-[var(--glass-border)] p-6">
      <header className="flex flex-col gap-2 border-b border-zinc-200 pb-4">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">
            {signal.kind}
          </span>
          <span>
            {copy.statusPrefix} {signal.status}
          </span>
          {typeof signal.confidence === "number" && (
            <span>
              {copy.confidencePrefix} {signal.confidence.toFixed(2)}
            </span>
          )}
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-900">{signal.summary}</h1>
        <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
          {decided && (
            <span>
              {copy.decidedPrefix} {decided}
            </span>
          )}
          {updated && (
            <span>
              {copy.updatedPrefix} {updated}
            </span>
          )}
        </div>
      </header>

      {signal.body && (
        <section>
          <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
            {copy.detail}
          </h2>
          <p className="text-sm whitespace-pre-line text-zinc-800">{signal.body}</p>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
          {copy.sources}
        </h2>
        <SignalSourceList sources={signal.sources} />
      </section>

      {signal.activity.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
            {copy.activity}
          </h2>
          <ul className="flex flex-col gap-1.5 text-sm">
            {signal.activity.map((activity) => {
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
