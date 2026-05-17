/* SSE parser: yields typed AgentEvents from a fetch response body. */

import type { AgentEvent, AgentEventType } from "@/lib/types";

const EVENT_LINE = /^event:\s*(.+)$/;
const DATA_LINE = /^data:\s*(.*)$/;

export async function* parseAgentStream(response: Response): AsyncGenerator<AgentEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separator: number;
    while ((separator = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const event = parseChunk(chunk);
      if (event) yield event;
    }
  }
}

function parseChunk(chunk: string): AgentEvent | null {
  let eventType: AgentEventType | null = null;
  let dataLine: string | null = null;
  for (const rawLine of chunk.split("\n")) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) continue;
    const eventMatch = EVENT_LINE.exec(line);
    if (eventMatch) {
      eventType = eventMatch[1].trim() as AgentEventType;
      continue;
    }
    const dataMatch = DATA_LINE.exec(line);
    if (dataMatch) {
      dataLine = dataLine === null ? dataMatch[1] : `${dataLine}\n${dataMatch[1]}`;
    }
  }
  if (!eventType) return null;
  let data: Record<string, unknown> = {};
  if (dataLine) {
    try {
      data = JSON.parse(dataLine) as Record<string, unknown>;
    } catch {
      data = { raw: dataLine };
    }
  }
  return { type: eventType, data };
}
