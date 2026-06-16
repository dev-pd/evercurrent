import { FileText, MessageSquare } from "lucide-react";
import type { InsightSource } from "@/lib/types";

interface InsightSourcesProps {
  sources: InsightSource[];
}

export function InsightSources({ sources }: InsightSourcesProps) {
  return (
    <section className="border-t border-[var(--color-accent-100)] bg-white/60 px-5 py-4">
      <h3 className="text-xs font-semibold tracking-wider text-[var(--text-secondary)] uppercase">
        Sources
      </h3>
      <ul className="mt-2 flex flex-col gap-1.5">
        {sources.map((source, idx) => (
          <li key={idx} className="flex items-start gap-2 text-xs">
            {source.kind === "slack" ? (
              <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
            ) : (
              <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-[var(--text-muted)]">
                {source.channel && <span className="font-medium">{source.channel}</span>}
                {source.author && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{source.author}</span>
                  </>
                )}
              </div>
              <p className="mt-0.5 text-[var(--text-primary)]">{source.snippet}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
