import { describe, expect, it } from "vitest"

import { initialState, toEntry } from "@/components/flow/cards"
import { unfrozenProposal } from "@/mocks/handlers"

import { isName, jobTarget, jobTitle, parseProtocolParam, protocolParam } from "./jobs"

describe("how the flow names things", () => {
  it("keeps the protocol in the URL and checks names", () => {
    expect(protocolParam({ source: "proposal", name: "p1" })).toBe("proposal:p1")
    expect(parseProtocolParam("repo:rag-factuality")).toEqual({ source: "repo", name: "rag-factuality" })
    for (const bad of ["repo:../x", "elsewhere:x", "repo:", null]) expect(parseProtocolParam(bad)).toBeNull()
    expect(isName("rag-tpl-s2")).toBe(true)
    for (const bad of ["-rf", ".hidden", "a/b", "a b", ""]) expect(isName(bad)).toBe(false)
  })
  it("titles a job and links what it writes", () => {
    expect(jobTitle({ kind: "run", refs: { run: "cascade~c1", corpus: "c1" } })).toBe("engine run cascade~c1")
    expect(jobTarget({ kind: "score", refs: { score: "cascade~c1" } })).toBe("/scores/reports/cascade~c1")
    expect(jobTarget({ kind: "compare", refs: { score: "compare-c1" } })).toBe("/scores/compares/compare-c1")
    expect(jobTarget({ kind: "synth", refs: { corpus_set: "c", corpus: "c-mixed" } })).toBe("/corpora/c-mixed")
  })
})

describe("the cards form's entries", () => {
  const [screen] = unfrozenProposal("p1").cards
  it("starts at the model's default, by the model", () => {
    const s = initialState(screen)
    expect(s).toMatchObject({ choice: screen.default, by: "model" })
    expect(s.reason).toMatch(/^default: /)
    expect(toEntry(screen, s)).toEqual({ entry: { card: "screen", choice: screen.default, reason: s.reason, by: "model", value: null }, error: null })
  })
  it("refuses an empty reason and custom JSON that does not parse; sends a custom value", () => {
    const s = initialState(screen)
    expect(toEntry(screen, { ...s, reason: "  " }).error).toBe("a reason is required")
    expect(toEntry(screen, { ...s, choice: "custom", custom: "{nope", by: "user" }).error).toBe("the custom value is not JSON")
    const custom = toEntry(screen, { ...s, choice: "custom", custom: '{"question": "Q?", "terms": ["RAG"]}', reason: "narrower", by: "user" })
    expect(custom).toEqual({ entry: { card: "screen", choice: "custom", reason: "narrower", by: "user", value: { question: "Q?", terms: ["RAG"] } }, error: null })
  })
})
