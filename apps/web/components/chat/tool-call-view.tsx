"use client";

import { useState } from "react";

interface ToolCallViewProps {
  name: string;
  input: Record<string, unknown>;
  result?: unknown;
}

export function ToolCallView({ name, input, result }: ToolCallViewProps) {
  const [open, setOpen] = useState(false);
  const resultPreview = renderPreview(result);
  return (
    <div className="my-2 rounded-md border border-zinc-200 bg-zinc-50 text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left font-mono text-zinc-600"
      >
        <span>
          <span className="text-zinc-400">tool</span> {name}
        </span>
        <span className="text-zinc-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-zinc-200 px-3 py-2">
          <details>
            <summary className="cursor-pointer text-zinc-500">input</summary>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-zinc-700">
              {JSON.stringify(input, null, 2)}
            </pre>
          </details>
          <details open>
            <summary className="cursor-pointer text-zinc-500">result</summary>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-zinc-700">
              {resultPreview}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}

function renderPreview(result: unknown): string {
  if (result === undefined) return "(pending)";
  if (typeof result === "string") return result;
  try {
    const text = JSON.stringify(result, null, 2);
    if (text.length > 1200) return `${text.slice(0, 1200)}\n…(truncated)`;
    return text;
  } catch {
    return String(result);
  }
}
