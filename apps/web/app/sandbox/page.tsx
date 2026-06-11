"use client";

import { useState } from "react";
import {
  WireframeFocused,
  WireframeWorkspace,
  WireframeTriage,
  WireframeDecisions,
  WireframeTimeline,
  WireframeEve,
  WireframeSettings,
} from "@/components/sandbox/wireframes";

type Item = { id: string; name: string; blurb: string; render: () => React.ReactNode };

const STRUCTURES: Item[] = [
  {
    id: "focused",
    name: "A · Focused digest",
    blurb: "Few pages, digest is king, Eve inline. Simplest.",
    render: () => <WireframeFocused />,
  },
  {
    id: "workspace",
    name: "B · Workspace (3-pane)",
    blurb: "Left context + center + Eve always on the right. Most platform.",
    render: () => <WireframeWorkspace />,
  },
  {
    id: "triage",
    name: "C · Triage hub",
    blurb: "One inbox, Decisions/Timeline as views. Email/Linear feel.",
    render: () => <WireframeTriage />,
  },
];

const PAGES: Item[] = [
  { id: "decisions", name: "Decisions", blurb: "", render: () => <WireframeDecisions /> },
  { id: "timeline", name: "Timeline", blurb: "", render: () => <WireframeTimeline /> },
  { id: "eve", name: "Eve / Insights", blurb: "", render: () => <WireframeEve /> },
  { id: "settings", name: "Settings", blurb: "", render: () => <WireframeSettings /> },
];

export default function SandboxPage() {
  const [active, setActive] = useState<string>("focused");
  const current = [...STRUCTURES, ...PAGES].find((o) => o.id === active) ?? STRUCTURES[0];

  return (
    <main className="min-h-screen bg-zinc-100 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6">
          <h1 className="text-lg font-semibold text-zinc-900">Structure sandbox</h1>
          <p className="mt-1 text-sm text-zinc-500">
            How the whole app is organized — pages, panels, where each feature lives. Wireframes,
            not colors. Pick a structure; preview every page.
          </p>
        </header>

        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
          App structure
        </p>
        <div className="mb-5 flex flex-wrap gap-2">
          {STRUCTURES.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => setActive(o.id)}
              className={`max-w-xs rounded-lg border px-4 py-2 text-left transition-colors ${
                active === o.id
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300"
              }`}
            >
              <div className="text-sm font-semibold">{o.name}</div>
              <div className={`mt-0.5 text-xs ${active === o.id ? "text-zinc-300" : "text-zinc-400"}`}>
                {o.blurb}
              </div>
            </button>
          ))}
        </div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
          The other pages
        </p>
        <div className="mb-5 flex flex-wrap gap-2">
          {PAGES.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => setActive(o.id)}
              className={`rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
                active === o.id
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300"
              }`}
            >
              {o.name}
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
          {current.render()}
        </div>
      </div>
    </main>
  );
}
