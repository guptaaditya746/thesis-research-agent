import { describe, expect, it } from "vitest"

import type { Answer } from "@/api/types"

import { walkTargetForClaims } from "./walk-context"

const fact = (id: string, claims: string[]) => ({ id, s: "p1", p: "evaluatesOn", o: id, claims, origin: "research" })
const answer: Answer = {
  concept_sha256: "0".repeat(64),
  kind: "graph",
  rows: [
    { id: "r1", facts: [fact("f1", ["c1", "c2"])] },
    { id: "r2", facts: [fact("f2", ["c3"])] },
    { id: "r3", facts: [fact("f3", ["c3"])] },
  ],
}

describe("walkTargetForClaims", () => {
  it("opens the walk of the one fact that cites every claim", () => {
    expect(walkTargetForClaims(["c1"], answer)).toEqual({ kind: "fact", factId: "f1" })
    expect(walkTargetForClaims(["c1", "c2"], answer)).toEqual({ kind: "fact", factId: "f1" })
  })

  it("walks all the claims of a merged edge whose claims back different facts, or none", () => {
    expect(walkTargetForClaims(["c1", "c3"], answer, "evaluatesOn")).toEqual({
      kind: "claims", claimIds: ["c1", "c3"], label: "evaluatesOn", citedBy: { c1: ["f1"], c3: ["f2", "f3"] },
    })
    // one claim cited, one not: the uncited one's evidence is not dropped
    expect(walkTargetForClaims(["c1", "c9"], answer)).toMatchObject({ kind: "claims", citedBy: { c1: ["f1"], c9: [] } })
    // a claim two facts cite
    expect(walkTargetForClaims(["c3"], answer)).toMatchObject({ kind: "claims", citedBy: { c3: ["f2", "f3"] } })
    expect(walkTargetForClaims(["c9"], null)).toMatchObject({ kind: "claims", citedBy: { c9: [] } })
  })
})
