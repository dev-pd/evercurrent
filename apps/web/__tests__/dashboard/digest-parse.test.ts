import { describe, expect, test } from "vitest";
import { parseDigest } from "@/lib/digest-parse";

describe("parseDigest", () => {
  test("strips [signal:…] and [msg:…] citation tokens from the rendered text", () => {
    const md = [
      "## Top priority",
      "- **Lock BRK-A1 to AL-7075-T6** before the gate [signal:d81b219b-1a40-4d78-86fb-c0a0e9de3b3f]",
      "- Distributor allocation still open [msg:11111111-2222-3333-4444-555555555555]",
    ].join("\n");

    const { top_priority } = parseDigest(md);

    expect(top_priority).toHaveLength(2);
    expect(top_priority[0].text).toBe("Lock BRK-A1 to AL-7075-T6 before the gate");
    expect(top_priority[0].text).not.toContain("signal:");
    // [msg:…] is still captured as the linkable message id, just not shown in text.
    expect(top_priority[1].text).toBe("Distributor allocation still open");
    expect(top_priority[1].messageId).toBe("11111111-2222-3333-4444-555555555555");
  });
});
