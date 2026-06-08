import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";

function Hello({ name }: { name: string }) {
  return <p>Hello, {name}</p>;
}

describe("smoke", () => {
  test("vitest + RTL renders a component", () => {
    render(<Hello name="EverCurrent" />);
    expect(screen.getByText(/hello, evercurrent/i)).toBeInTheDocument();
  });
});
