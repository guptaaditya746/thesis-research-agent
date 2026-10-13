import { describe, expect, it } from "vitest"

import { PASSAGES } from "@/mocks/fixtures"

import { splitPassage } from "./passage"

describe("splitPassage", () => {
  it("cuts the window at the anchor, in file offsets", () => {
    const parts = splitPassage(PASSAGES.spider)
    expect(parts.match).toBe("deployable LLMs using benchmark datasets like Spider and Bird")
    expect(parts.before.endsWith("open-source, ")).toBe(true)
    expect(parts.after.startsWith(". However")).toBe(true)
    expect(parts.clamped).toBe(false)
    expect(parts.before + parts.match + parts.after).toBe(PASSAGES.spider.text)
  })

  it("works for a window that starts at the top of the file", () => {
    expect(splitPassage(PASSAGES.megapairs).match).toBe("MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval")
  })

  it("clamps an anchor outside the window instead of throwing", () => {
    const parts = splitPassage({ text: "abcdef", offset: 100, highlight: { start: 98, end: 103 } })
    expect(parts).toEqual({ before: "", match: "abc", after: "def", clamped: true })
    expect(splitPassage({ text: "abc", offset: 0, highlight: { start: 10, end: 20 } })).toMatchObject({ match: "", clamped: true })
  })
})
