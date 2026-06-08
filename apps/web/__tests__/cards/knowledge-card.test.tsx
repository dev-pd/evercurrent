import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { KnowledgeCard } from "@/components/cards/knowledge-card";
import type { CardResponse } from "@/lib/types";

const card: CardResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  kind: "decision",
  summary: "Switch BRK-A1 from AL-6063-T5 to AL-7075-T6",
  body: "Change chassis bracket material in two high-flux regions to fix thermal margin.",
  status: "decided",
  confidence: 0.95,
  decided_at: "2026-06-06T10:00:00Z",
  updated_at: "2026-06-07T10:00:00Z",
  sources: [
    {
      id: "22222222-2222-2222-2222-222222222222",
      kind: "message",
      channel: "#mech-design",
      author_display_name: "Sarah",
      author_username: "sarah",
      ts: "2026-06-06T06:14:00Z",
      text: "Drafted ECO-178 for the chassis material switch.",
      url: null,
    },
  ],
  edges: [
    {
      id: "33333333-3333-3333-3333-333333333333",
      kind: "blocks",
      target_card_id: "44444444-4444-4444-4444-444444444444",
      target_label: "DVT exit",
    },
  ],
  activity: [],
};

describe("KnowledgeCard", () => {
  test("renders summary, body, sources, and edges", () => {
    render(<KnowledgeCard card={card} />);
    expect(screen.getByText(/switch brk-a1/i)).toBeInTheDocument();
    expect(screen.getByText(/chassis bracket material/i)).toBeInTheDocument();
    expect(screen.getByText(/#mech-design/)).toBeInTheDocument();
    expect(screen.getByText(/dvt exit/i)).toBeInTheDocument();
  });
});
