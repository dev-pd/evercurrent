/** Monochrome structural wireframes — about layout + feature placement, not color. */

function Box({
  label,
  sub,
  className = "",
  tall = false,
}: {
  label: string;
  sub?: string;
  className?: string;
  tall?: boolean;
}) {
  return (
    <div
      className={`flex flex-col rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-2.5 ${
        tall ? "min-h-[120px]" : ""
      } ${className}`}
    >
      <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-600">
        {label}
      </span>
      {sub && <span className="mt-0.5 text-[10px] leading-snug text-zinc-400">{sub}</span>}
    </div>
  );
}

function Win({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-300 bg-white shadow-sm">
      <div className="flex items-center gap-1.5 border-b border-zinc-200 bg-zinc-100 px-3 py-1.5">
        <span className="h-2 w-2 rounded-full bg-zinc-300" />
        <span className="h-2 w-2 rounded-full bg-zinc-300" />
        <span className="h-2 w-2 rounded-full bg-zinc-300" />
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function Caption({ pages, mapping }: { pages: string; mapping: string[] }) {
  return (
    <div className="mt-4 rounded-md bg-zinc-50 p-3 text-xs">
      <div className="text-zinc-700">
        <span className="font-semibold">Pages:</span> {pages}
      </div>
      <ul className="mt-2 space-y-1 text-zinc-500">
        {mapping.map((m) => (
          <li key={m}>• {m}</li>
        ))}
      </ul>
    </div>
  );
}

/* A — Focused digest: few pages, digest is king, Eve folded inline. */
export function WireframeFocused() {
  return (
    <div>
      <Win>
        <div className="flex gap-3">
          <div className="w-28 shrink-0 space-y-1.5">
            <Box label="Nav" sub="Digest" />
            <Box label="" sub="Decisions" />
            <Box label="" sub="Timeline" />
            <Box label="" sub="Settings" />
          </div>
          <div className="flex-1 space-y-2">
            <Box label="Context bar" sub="You · role · phase · day · View-as ▾" />
            <Box label="AI summary" sub="“2 things need you today” + Eve alert inline" />
            <div className="grid grid-cols-3 gap-2">
              <Box label="Top priority" tall />
              <Box label="Watch-outs" tall />
              <Box label="FYI" tall />
            </div>
          </div>
        </div>
      </Win>
      <Caption
        pages="Digest · Decisions · Timeline · Settings (4)"
        mapping={[
          "Digest is THE page; everything orbits it.",
          "Eve insights + cross-role alerts shown inline on the digest (no separate page).",
          "Connectors + Subscriptions folded into Settings.",
          "Best when: you want laser focus on the brief. Fewest pages.",
        ]}
      />
    </div>
  );
}

/* B — Workspace: 3-pane, left context, center view, right Eve always-on. */
export function WireframeWorkspace() {
  return (
    <div>
      <Win>
        <div className="flex gap-3">
          <div className="w-28 shrink-0 space-y-1.5">
            <Box label="Project ▾" sub="phase: DVT" />
            <Box label="Subsystems" sub="chassis·power·qa" />
            <Box label="View-as" sub="Raj ▾" />
            <Box label="Nav" sub="Digest/Dec/Time" />
          </div>
          <div className="flex-1 space-y-2">
            <Box label="Center: active view" sub="digest / decisions / timeline" />
            <div className="grid grid-cols-3 gap-2">
              <Box label="Top" tall />
              <Box label="Watch" tall />
              <Box label="FYI" tall />
            </div>
          </div>
          <div className="w-28 shrink-0 space-y-1.5">
            <Box label="EVE" sub="proactive insights" tall />
            <Box label="Cross-role" sub="power→your thermal" />
          </div>
        </div>
      </Win>
      <Caption
        pages="Digest · Decisions · Timeline · Settings — inside one shell (3-pane)"
        mapping={[
          "Left rail = context (project, phase, subsystems, View-as) + nav.",
          "Center = whatever you're working on (digest by default).",
          "Right = Eve agent + cross-role alerts, ALWAYS visible.",
          "Best when: you want the agent + context present at all times. Most 'platform'.",
        ]}
      />
    </div>
  );
}

/* ---- The other pages (shown under structure A: own page, with persistent
   left nav; lists scroll internally so the page never grows). ---- */

export function WireframeDecisions() {
  return (
    <div>
      <Win>
        <div className="flex gap-3">
          <div className="w-24 shrink-0 space-y-1.5">
            <Box label="Nav" sub="Decisions" />
          </div>
          <div className="flex-1 space-y-2">
            <Box label="Filters" sub="subsystem · status · phase · who" />
            <div className="grid grid-cols-[1fr_180px] gap-2">
              <div className="space-y-1.5">
                <Box label="▸ Decision" sub="Compress to Sep 15 FCS · Mei · supply · open" />
                <Box label="▸ Decision" sub="Samsung cell swap · Dan · power · confirmed" />
                <Box label="▸ Risk" sub="AlumWest sole source · supply · open" />
                <Box label="▸ Decision" sub="ECO-184 clip shorten · mech · confirmed" />
              </div>
              <Box label="Detail" sub="rationale · who/when · sources · affected subsystems · linked cards" tall />
            </div>
          </div>
        </div>
      </Win>
      <Caption
        pages="Decisions — the team's memory"
        mapping={[
          "Left = filterable list of extracted decisions/risks (scrolls internally).",
          "Right = detail: rationale, who/when, source threads, affected subsystems, cross-links.",
          "Powered by the decision-extractor agent (needs cards generated — currently 0).",
        ]}
      />
    </div>
  );
}

export function WireframeTimeline() {
  return (
    <div>
      <Win>
        <div className="space-y-2">
          <Box label="Atlas — DVT · Day 42" sub="Sep 15 FCS · ~31% through NPI plan" />
          <div className="grid grid-cols-6 gap-1">
            {["Apr", "May", "Jun", "Jul", "Aug", "Sep"].map((m) => (
              <div key={m} className="text-center text-[10px] text-zinc-400">
                {m}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-4 gap-1">
            <Box label="EVT done" />
            <Box label="DVT active" className="border-zinc-500 bg-zinc-100" />
            <Box label="PVT" />
            <Box label="MP" />
          </div>
          <div className="space-y-1">
            {["chassis", "power", "firmware", "qa", "supply"].map((s) => (
              <Box key={s} label={s} sub="▬▬▬▬▬◆▭▭ progress + today marker" />
            ))}
          </div>
        </div>
      </Win>
      <Caption
        pages="Timeline — where the program is"
        mapping={[
          "Phase ladder (EVT→DVT→PVT→MP) + per-subsystem lanes + 'today' marker.",
          "Already wired to real project data (Atlas/DVT/day 42).",
          "Add: milestones / phase-gate readiness per subsystem.",
        ]}
      />
    </div>
  );
}

export function WireframeEve() {
  return (
    <div>
      <Win>
        <div className="space-y-2">
          <Box label="EVE · proactive insight" sub="REQ-245 · detected 2h ago" />
          <div className="grid grid-cols-2 gap-2">
            <Box label="Before" sub="torque 15 Nm · margin 13%" />
            <Box label="After" sub="torque 22 Nm · margin -4%" className="border-zinc-500" />
          </div>
          <Box label="Conflicts" sub="chassis: mass >10kg · power: +12°C · supply: +$3.40/unit" />
          <Box label="Impact" sub="cost +$3.40 · schedule +2wk · revenue $182k at risk" />
          <Box label="Suggested action" sub="loop in Sarah·Dan·Raj·Mei before design freeze" />
        </div>
      </Win>
      <Caption
        pages="Eve — proactive cross-team agent"
        mapping={[
          "Detects high-impact, cross-subsystem changes (a spec moves → who it breaks).",
          "Before/after + conflicts + cost/schedule impact + suggested meeting.",
          "In structure A this appears inline on the digest; in B it's the right rail.",
          "Generation pipeline not built yet (returns empty).",
        ]}
      />
    </div>
  );
}

export function WireframeSettings() {
  return (
    <div>
      <Win>
        <div className="flex gap-3">
          <div className="w-24 shrink-0 space-y-1.5">
            <Box label="Nav" sub="Settings" />
          </div>
          <div className="flex-1 space-y-2">
            <Box label="Profile" sub="role · owned subsystems · timezone" />
            <Box label="Subscriptions" sub="topics / people / subsystems you follow" />
            <Box label="Delivery" sub="in-app · Slack DM · email · time" />
            <Box label="Sources" sub="Slack ✓ connected · Drive — · last sync 2m" />
          </div>
        </div>
      </Win>
      <Caption
        pages="Settings — tune your digest (Connectors fold in here)"
        mapping={[
          "Profile + subscriptions + delivery + Sources strip (no separate Connectors page).",
          "This is where 'personalize / adapt' is user-controlled.",
        ]}
      />
    </div>
  );
}

/* C — Triage hub: one inbox of items, filters become views, detail on right. */
export function WireframeTriage() {
  return (
    <div>
      <Win>
        <div className="flex gap-3">
          <div className="w-28 shrink-0 space-y-1.5">
            <Box label="Views" sub="My day" />
            <Box label="" sub="By subsystem" />
            <Box label="" sub="Decisions" />
            <Box label="" sub="Timeline" />
          </div>
          <div className="flex-1 space-y-2">
            <Box label="Filters" sub="priority · subsystem · type · role" />
            <Box label="▸ item" sub="ExtruCo strike → you" />
            <Box label="▸ item" sub="ECO-184 mass add" />
            <Box label="▸ item" sub="BOM cost drift" />
          </div>
          <div className="w-32 shrink-0">
            <Box label="Detail" sub="thread · related decision · cross-role · feedback" tall />
          </div>
        </div>
      </Win>
      <Caption
        pages="One Inbox + saved Views (Decisions, Timeline are filters) · Settings"
        mapping={[
          "Everything is one stream of items you triage (like email/Linear).",
          "Digest = a default 'view'; Decisions/by-subsystem = other views.",
          "Click an item → detail pane (thread, decision, cross-role, feedback).",
          "Best when: high message volume + you want to 'work through' your day.",
        ]}
      />
    </div>
  );
}
