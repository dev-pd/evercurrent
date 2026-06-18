import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { StalenessBanner } from "@/components/dashboard/staleness-banner";

describe("StalenessBanner", () => {
  test("summarizes resolved signals and new messages", () => {
    render(<StalenessBanner resolvedSignals={2} newMessages={5} />);
    expect(
      screen.getByText(/2 signals resolved · 5 new messages since this digest/i),
    ).toBeInTheDocument();
  });

  test("uses singular wording for a single signal and message", () => {
    render(<StalenessBanner resolvedSignals={1} newMessages={1} />);
    expect(
      screen.getByText(/1 signal resolved · 1 new message since this digest/i),
    ).toBeInTheDocument();
  });
});
