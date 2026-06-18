import { cn } from "@/lib/utils";

const TRACES = [
  "M200 160 H120 V70 H64",
  "M200 160 H300 V70 H338",
  "M200 160 V250 H110",
  "M200 160 V250 H300 V210",
  "M200 160 H80 V210",
] as const;

const NODES = [
  { cx: 64, cy: 70 },
  { cx: 338, cy: 70 },
  { cx: 110, cy: 250 },
  { cx: 300, cy: 210 },
  { cx: 80, cy: 210 },
] as const;

/**
 * Decorative PCB graphic for the landing hero: a central chip with traces
 * fanning out to nodes, and "current" pulses animating along the traces.
 * Pure inline SVG (SMIL) — no JS, no deps.
 */
export function CircuitArt({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 320"
      role="img"
      aria-label="Stylized circuit board"
      className={cn("h-auto w-full max-w-md", className)}
      fill="none"
    >
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path
            d="M20 0 H0 V20"
            stroke="var(--border-default)"
            strokeWidth="0.5"
            opacity="0.5"
          />
        </pattern>
      </defs>

      <rect x="0" y="0" width="400" height="320" fill="url(#grid)" />

      {TRACES.map((d) => (
        <path
          key={d}
          d={d}
          stroke="var(--color-accent-600)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.45"
        />
      ))}

      {NODES.map((n) => (
        <circle
          key={`${n.cx}-${n.cy}`}
          cx={n.cx}
          cy={n.cy}
          r="5"
          fill="var(--surface-bg)"
          stroke="var(--color-accent-600)"
          strokeWidth="2"
        />
      ))}

      {TRACES.slice(0, 4).map((d, i) => (
        <circle key={`pulse-${d}`} r="3" fill="var(--color-accent-600)">
          <animateMotion
            dur="2.6s"
            begin={`${i * 0.55}s`}
            repeatCount="indefinite"
            path={d}
            rotate="auto"
            keyPoints="1;0"
            keyTimes="0;1"
            calcMode="linear"
          />
        </circle>
      ))}

      {/* central chip */}
      <rect
        x="160"
        y="130"
        width="80"
        height="60"
        rx="8"
        fill="white"
        stroke="var(--color-accent-600)"
        strokeWidth="2"
      />
      {[148, 168, 188].map((y) => (
        <line
          key={`pin-l-${y}`}
          x1="150"
          y1={y}
          x2="160"
          y2={y}
          stroke="var(--color-accent-600)"
          strokeWidth="2"
        />
      ))}
      {[148, 168, 188].map((y) => (
        <line
          key={`pin-r-${y}`}
          x1="240"
          y1={y}
          x2="250"
          y2={y}
          stroke="var(--color-accent-600)"
          strokeWidth="2"
        />
      ))}
      <rect x="178" y="148" width="44" height="24" rx="3" fill="var(--color-accent-600)" opacity="0.15" />
    </svg>
  );
}
