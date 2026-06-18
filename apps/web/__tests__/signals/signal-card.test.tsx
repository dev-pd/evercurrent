import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { SignalCard } from "@/components/signals/signal-card";
import type { SignalResponse } from "@/lib/types";

const signal: SignalResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  kind: "decision",
  summary: "Switch BRK-A1 from AL-6063-T5 to AL-7075-T6",
  body: "Change chassis bracket material in two high-flux regions to fix thermal margin.",
  status: "decided",
  confidence: 0.95,
  decided_at: "2026-06-06T10:00:00Z",
  updated_at: "2026-06-07T10:00:00Z",
  affected_subsystems: ["thermal", "chassis"],
  affected_roles: ["mech"],
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
  activity: [],
};

describe("SignalCard", () => {
  test("renders summary, body, and sources", () => {
    render(<SignalCard signal={signal} />);
    expect(screen.getByText(/switch brk-a1/i)).toBeInTheDocument();
    expect(screen.getByText(/chassis bracket material/i)).toBeInTheDocument();
    expect(screen.getByText(/#mech-design/)).toBeInTheDocument();
  });
});
