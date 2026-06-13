export const SUBSYSTEMS = [
  "chassis",
  "power",
  "bms",
  "firmware",
  "thermal",
  "qa",
  "supply",
  "manufacturing",
] as const;

const COLOR: Record<string, string> = {
  chassis: "#64748b",
  power: "#f59e0b",
  bms: "#10b981",
  firmware: "#6366f1",
  thermal: "#ef4444",
  qa: "#22c55e",
  supply: "#a855f7",
  manufacturing: "#f97316",
};

export function subsystemColor(name: string): string {
  const key = name.toLowerCase();
  for (const k of Object.keys(COLOR)) {
    if (key.includes(k)) return COLOR[k];
  }
  return "#818cf8";
}
