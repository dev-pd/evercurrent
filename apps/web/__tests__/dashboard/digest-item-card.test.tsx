import { describe, expect, test, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DigestItemCard } from "@/components/dashboard/digest-item-card";
import type { DigestItemV2 } from "@/lib/types";

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const baseItem: DigestItemV2 = {
  id: "11111111-1111-1111-1111-111111111111",
  bucket: "top_priority",
  source: "#mech-design",
  author_display_name: "Sarah Chen",
  ts: "2026-06-07T13:00:00Z",
  why_this_matters: "ECO-178 fast-track closes today.",
  card_id: "22222222-2222-2222-2222-222222222222",
  message_id: null,
};

describe("DigestItemCard", () => {
  test("renders source line and why-this-matters", () => {
    wrap(<DigestItemCard item={baseItem} />);
    expect(screen.getByText(/#mech-design/)).toBeInTheDocument();
    expect(screen.getByText(/ECO-178/)).toBeInTheDocument();
  });

  test("shows 'Open card' link when card_id present", () => {
    wrap(<DigestItemCard item={baseItem} />);
    expect(screen.getByRole("link", { name: /open card/i })).toBeInTheDocument();
  });

  test("hides 'Open card' link when card_id missing", () => {
    wrap(<DigestItemCard item={{ ...baseItem, card_id: null }} />);
    expect(screen.queryByRole("link", { name: /open card/i })).toBeNull();
  });

  test("thumbs up fires onFeedback with useful=true", () => {
    const onFeedback = vi.fn();
    wrap(<DigestItemCard item={baseItem} onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: /^useful$/i }));
    expect(onFeedback).toHaveBeenCalledWith({
      cardId: baseItem.card_id,
      useful: true,
    });
  });

  test("thumbs down fires onFeedback with useful=false", () => {
    const onFeedback = vi.fn();
    wrap(<DigestItemCard item={baseItem} onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: /not useful/i }));
    expect(onFeedback).toHaveBeenCalledWith({
      cardId: baseItem.card_id,
      useful: false,
    });
  });
});
