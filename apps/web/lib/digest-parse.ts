import type { DigestItemV2 } from "@/lib/types";

type Bucket = DigestItemV2["bucket"];

export interface DigestBullet {
  text: string;
  messageId: string | null;
}

export type ParsedDigest = Record<Bucket, DigestBullet[]>;

const HEADER_TO_BUCKET: Record<string, Bucket> = {
  "top priority": "top_priority",
  "top priorities": "top_priority",
  "watch-outs": "watch_outs",
  "watch outs": "watch_outs",
  watchouts: "watch_outs",
  fyi: "fyi",
  "for your information": "fyi",
};

export function parseDigest(md: string | null | undefined): ParsedDigest {
  const out: ParsedDigest = { top_priority: [], watch_outs: [], fyi: [] };
  if (!md) return out;
  let current: Bucket | null = null;

  for (const raw of md.split("\n")) {
    const line = raw.trim();
    const header = line.match(/^#{1,4}\s+(.*)$/);
    if (header) {
      const key = header[1]
        .toLowerCase()
        .replace(/[*:_`]/g, "")
        .trim();
      current = HEADER_TO_BUCKET[key] ?? null;
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet && current) {
      const body = bullet[1];
      const cite = body.match(/\[msg:([0-9a-fA-F-]+)\]/);
      const messageId = cite ? cite[1] : null;
      const text = body
        // Strip every citation token the digest LLM emits — [msg:…],
        // [message:…], [signal:…] — so none leak into the rendered text.
        .replace(/\s*\[(?:msg|message|signal):[0-9a-fA-F-]+\]\s*/g, " ")
        .replace(/\*\*/g, "")
        .trim();
      if (text) out[current].push({ text, messageId });
    }
  }
  return out;
}
