type TimestampStyle = "datetime" | "date" | "time";

const STYLE_OPTIONS: Record<TimestampStyle, Intl.DateTimeFormatOptions> = {
  datetime: { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" },
  date: { month: "short", day: "numeric" },
  time: { hour: "2-digit", minute: "2-digit" },
};

/** Format an ISO timestamp for display. Returns null for empty input and the
 *  raw string if it can't be parsed (so a bad value never crashes a signal). */
export function formatTimestamp(
  iso: string | null | undefined,
  style: TimestampStyle = "datetime",
): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, STYLE_OPTIONS[style]);
}

/** Coarse relative age ("today", "3d ago", "2w ago") for list timestamps. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
}
