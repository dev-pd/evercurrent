"use client";

import { ToolCallView } from "@/components/chat/tool-call-view";
import { Button } from "@/components/ui/button";
import { useAgent } from "@/hooks/use-agent";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ChatPanel() {
  const { turns, ask, error } = useAgent();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns]);

  const submit = () => {
    const value = input.trim();
    if (!value) return;
    setInput("");
    void ask(value);
  };

  return (
    <div className="flex h-full w-[420px] shrink-0 flex-col border-l border-zinc-200 bg-white">
      <header className="border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-semibold">Ask EverCurrent</h2>
        <p className="text-xs text-zinc-500">Reasoning agent with 6 tools. Cites sources by id.</p>
      </header>
      <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-3 text-sm">
        {turns.length === 0 && (
          <div className="text-xs text-zinc-500">
            Try: <em>“What should I worry about this week?”</em> or{" "}
            <em>“What is the torque spec for the chassis motor?”</em>
          </div>
        )}
        {turns.map((turn) => (
          <div key={turn.id} className="mb-4">
            {turn.role === "user" ? (
              <div className="rounded-md bg-zinc-100 p-3 text-zinc-800">{turn.text}</div>
            ) : (
              <div>
                {turn.toolCalls.map((call) => (
                  <ToolCallView
                    key={call.id}
                    name={call.name}
                    input={call.input}
                    result={call.result}
                  />
                ))}
                {turn.text && (
                  <article className="prose prose-sm prose-zinc max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.text}</ReactMarkdown>
                  </article>
                )}
                {turn.streaming && <p className="text-xs text-zinc-400">streaming…</p>}
              </div>
            )}
          </div>
        ))}
        {error && (
          <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
            {error}
          </p>
        )}
      </div>
      <footer className="border-t border-zinc-200 p-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask anything…  (Cmd/Ctrl+Enter to send)"
          rows={3}
          className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:ring-2 focus:ring-zinc-950 focus:outline-none"
        />
        <div className="mt-2 flex justify-end">
          <Button size="sm" onClick={submit}>
            Send
          </Button>
        </div>
      </footer>
    </div>
  );
}
