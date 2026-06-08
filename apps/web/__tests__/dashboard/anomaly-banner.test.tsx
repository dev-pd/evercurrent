import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnomalyBanner } from "@/components/dashboard/anomaly-banner";
import type { DigestAnomaly } from "@/lib/types";

const anomalies: DigestAnomaly[] = [
  {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    summary: "Gripper resonance band may collide with motor mount torque spec.",
    card_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  },
];

describe("AnomalyBanner", () => {
  test("hides when empty", () => {
    const { container } = render(<AnomalyBanner anomalies={[]} />);
    expect(container.firstChild).toBeNull();
  });

  test("renders header and items when populated", () => {
    render(<AnomalyBanner anomalies={anomalies} />);
    expect(screen.getByText(/you might be missing/i)).toBeInTheDocument();
    expect(screen.getByText(/gripper resonance band/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      `/decisions/${anomalies[0].card_id}`,
    );
  });
});
