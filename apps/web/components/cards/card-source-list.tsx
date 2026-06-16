import { FileText, MessageSquare } from "lucide-react";
import { formatTimestamp } from "@/lib/format-date";
import type { CardSource } from "@/lib/types";

interface CardSourceListProps {
  sources: CardSource[];
}

function sourceIcon(kind: string) {
  if (kind === "message" || kind === "slack" || kind === "thread") {
    return <MessageSquare className="h-3.5 w-3.5 text-zinc-500" aria-hidden="true" />;
  }
  return <FileText className="h-3.5 w-3.5 text-zinc-500" aria-hidden="true" />;
}

export function CardSourceList({ sources }: CardSourceListProps) {
  if (sources.length === 0) {
    return <p className="text-xs text-zinc-500">No sources linked yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {sources.map((source) => {
        const ts = formatTimestamp(source.ts);
        return (
          <li key={source.id} className="rounded-md border border-zinc-200 bg-white p-3 text-sm">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              {sourceIcon(source.kind)}
              <span>{source.channel ?? source.kind}</span>
              {source.author_display_name && <span>· {source.author_display_name}</span>}
              {ts && <span>· {ts}</span>}
              {source.url && (
                <a
                  href={source.url}
                  {...(source.url.startsWith("slack:")
                    ? {}
                    : { target: "_blank", rel: "noreferrer" })}
                  className="ml-auto text-xs font-medium text-zinc-700 hover:text-zinc-900"
                >
                  Open in Slack
                </a>
              )}
            </div>
            <p className="mt-1 text-sm text-zinc-800">{source.text}</p>
          </li>
        );
      })}
    </ul>
  );
}
