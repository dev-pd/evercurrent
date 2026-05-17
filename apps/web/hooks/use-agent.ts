"use client";

import { api } from "@/lib/api";
import { parseAgentStream } from "@/lib/stream";
import type { AgentEvent } from "@/lib/types";
import { useImpersonationStore } from "@/stores/impersonation";
import { useCallback, useState } from "react";

export interface AgentTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  toolCalls: { id: string; name: string; input: Record<string, unknown>; result?: unknown }[];
  streaming: boolean;
}

export function useAgent() {
  const { currentProjectId, currentUserId } = useImpersonationStore();
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [error, setError] = useState<string | null>(null);

  const ask = useCallback(
    async (query: string) => {
      if (!currentProjectId || !currentUserId) {
        setError("Pick a user before asking.");
        return;
      }
      setError(null);
      const userTurn: AgentTurn = {
        id: crypto.randomUUID(),
        role: "user",
        text: query,
        toolCalls: [],
        streaming: false,
      };
      const assistantTurn: AgentTurn = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: "",
        toolCalls: [],
        streaming: true,
      };
      setTurns((prev) => [...prev, userTurn, assistantTurn]);

      try {
        const response = await fetch(api.agentChatUrl(currentProjectId), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Impersonate-User": currentUserId,
          },
          body: JSON.stringify({ query }),
        });
        if (!response.ok) {
          throw new Error(`agent HTTP ${response.status}`);
        }

        for await (const event of parseAgentStream(response)) {
          applyEvent(assistantTurn.id, event, setTurns);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setTurns((prev) =>
          prev.map((t) => (t.id === assistantTurn.id ? { ...t, streaming: false } : t)),
        );
      }
    },
    [currentProjectId, currentUserId],
  );

  return { turns, ask, error };
}

function applyEvent(
  turnId: string,
  event: AgentEvent,
  setTurns: React.Dispatch<React.SetStateAction<AgentTurn[]>>,
): void {
  setTurns((prev) =>
    prev.map((turn) => {
      if (turn.id !== turnId) return turn;
      const updated = { ...turn, toolCalls: [...turn.toolCalls] };
      if (event.type === "text_delta") {
        const text = typeof event.data.text === "string" ? event.data.text : "";
        updated.text = `${updated.text}${updated.text ? "\n\n" : ""}${text}`;
      } else if (event.type === "tool_use_start") {
        updated.toolCalls.push({
          id: String(event.data.id ?? crypto.randomUUID()),
          name: String(event.data.name ?? "tool"),
          input: (event.data.input as Record<string, unknown>) ?? {},
        });
      } else if (event.type === "tool_use_result") {
        const idx = updated.toolCalls.findIndex((c) => c.id === event.data.id);
        if (idx !== -1) {
          updated.toolCalls[idx] = {
            ...updated.toolCalls[idx],
            result: event.data.result,
          };
        }
      } else if (event.type === "done" || event.type === "close") {
        updated.streaming = false;
      }
      return updated;
    }),
  );
}
