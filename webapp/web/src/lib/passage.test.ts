import { describe, expect, it } from "vitest"

import { PASSAGES } from "@/mocks/fixtures"

import { splitPassage, utf16Index } from "./passage"

describe("splitPassage", () => {
  it("cuts the window at the highlight", () => {
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

  it("converts code points to UTF-16 when the backend sends only the code-point span", () => {
    // "𝑥" (U+1D465, math italic x, as converted PDFs have) is one code point but two UTF-16 units
    const text = "where 𝑥 is the input and 𝑦 the label"
    const start = [...text].indexOf("i") // code points: "where 𝑥 " = 8
    const passage = { text, highlight: { start, end: start + 12 }, highlight_utf16: null }
    expect(splitPassage(passage).match).toBe("is the input")
    // the backend's UTF-16 span wins when it is there
    expect(splitPassage({ ...passage, highlight_utf16: { start: 9, end: 21 } }).match).toBe("is the input")
  })

  it("clamps a span outside the window instead of throwing", () => {
    const parts = splitPassage({ text: "abcdef", highlight: { start: -2, end: 3 }, highlight_utf16: null })
    expect(parts).toEqual({ before: "", match: "abc", after: "def", clamped: true })
    expect(splitPassage({ text: "abc", highlight: { start: 10, end: 20 }, highlight_utf16: null })).toMatchObject({ match: "", clamped: true })
  })

  it("shows the whole window when there is no highlight", () => {
    expect(splitPassage({ text: "abc", highlight: null, highlight_utf16: null })).toEqual({ before: "abc", match: "", after: "", clamped: false })
  })
})

describe("utf16Index", () => {
  it("counts astral characters as two units", () => {
    expect(utf16Index("a𝑥b", 0)).toBe(0)
    expect(utf16Index("a𝑥b", 2)).toBe(3)
    expect(utf16Index("a𝑥b", 3)).toBe(4)
    expect(utf16Index("ab", 5)).toBe(5) // past the end: as many units as code points
  })
})
