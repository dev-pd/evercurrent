import { describe, expect, test } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { DecisionsBoard } from "@/components/decisions/decisions-board";
import type { SignalListItem } from "@/lib/types";

function makeSignal(overrides: Partial<SignalListItem>): SignalListItem {
  return {
    id: "00000000-0000-0000-0000-000000000000",
    kind: "decision",
    summary: "A signal",
    status: "open",
    sources_count: 1,
    affected_subsystems: [],
    updated_at: "2026-06-10T10:00:00Z",
    ...overrides,
  };
}

const openSignal = makeSignal({
  id: "11111111-1111-1111-1111-111111111111",
  summary: "Open decision about brackets",
  status: "open",
});

const resolvedSignal = makeSignal({
  id: "22222222-2222-2222-2222-222222222222",
  kind: "question",
  summary: "Resolved question about firmware",
  status: "resolved",
  resolved_at: "2026-06-12T10:00:00Z",
});

describe("DecisionsBoard", () => {
  test("the All open filter hides resolved signals", () => {
    render(<DecisionsBoard signals={[openSignal, resolvedSignal]} />);
    expect(screen.getByText(/open decision about brackets/i)).toBeInTheDocument();
    expect(screen.queryByText(/resolved question about firmware/i)).not.toBeInTheDocument();
  });

  test("the Resolved tab shows only resolved signals with a resolved-since line", () => {
    render(<DecisionsBoard signals={[openSignal, resolvedSignal]} />);

    fireEvent.click(screen.getByRole("button", { name: "Resolved" }));

    expect(screen.getByText(/resolved question about firmware/i)).toBeInTheDocument();
    expect(screen.queryByText(/open decision about brackets/i)).not.toBeInTheDocument();
    expect(screen.getByText(/resolved since/i)).toBeInTheDocument();
  });

  test("a resolved signal appears in All but not in the open Decisions filter", () => {
    render(<DecisionsBoard signals={[openSignal, resolvedSignal]} />);

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    const table = screen.getByRole("table");
    expect(within(table).getByText(/resolved question about firmware/i)).toBeInTheDocument();
    expect(within(table).getByText(/open decision about brackets/i)).toBeInTheDocument();
  });
});
