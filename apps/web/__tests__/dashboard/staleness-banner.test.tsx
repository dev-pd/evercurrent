import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { StalenessBanner } from "@/components/dashboard/staleness-banner";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("StalenessBanner", () => {
  test("summarizes resolved signals and new messages with a Regenerate button", () => {
    render(<StalenessBanner resolvedSignals={2} newMessages={5} />, { wrapper });
    expect(screen.getByText(/2 signals resolved · 5 new messages since this digest/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
  });

  test("uses singular wording for a single signal and message", () => {
    render(<StalenessBanner resolvedSignals={1} newMessages={1} />, { wrapper });
    expect(screen.getByText(/1 signal resolved · 1 new message since this digest/i)).toBeInTheDocument();
  });
});
