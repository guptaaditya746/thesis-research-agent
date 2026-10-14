import { describe, expect, it } from "vitest"

import { supportNote } from "./facts"

describe("supportNote", () => {
  it("counts what the support share counts: partial only when it counts as supported", () => {
    // scoring/support.py summarise: support_share = (supports + partial if partial_counts_as is yes) / facts
    expect(supportNote({ supports: 3, partial: 2, facts: 10, partial_counts_as: "yes" })).toBe(
      "5 of 10 facts supported by their quote (3 supported + 2 partial, which counts as supported)",
    )
    expect(supportNote({ supports: 3, partial: 2, facts: 10, partial_counts_as: "no" })).toBe("3 of 10 facts supported by their quote")
    expect(supportNote({ supports: 3, partial: 0, facts: 10, partial_counts_as: "yes" })).toBe("3 of 10 facts supported by their quote")
    expect(supportNote({ facts: 4 })).toBe("0 of 4 facts supported by their quote")
  })
})
