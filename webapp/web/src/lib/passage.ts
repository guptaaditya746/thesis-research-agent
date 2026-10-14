/**
 * The quote inside a corpus passage (claim walk, last link).
 *
 * GET /api/corpus/{paper} returns a window of the paper's text with the claim's span inside it:
 * `highlight` counts code points (Python, the anchors), `highlight_utf16` UTF-16 code units, which
 * is what JavaScript's `slice` takes; they differ after any character outside the BMP (math italic
 * letters in a converted PDF). The UTF-16 span is used when the backend sends it; the code-point
 * span is converted otherwise. The span is clamped to the window, so a stale anchor still renders
 * instead of throwing.
 */
import type { Highlight, Passage } from "@/api/types"

export interface PassageParts {
  before: string
  match: string
  after: string
  /** the highlight fell (partly) outside the window */
  clamped: boolean
}

/** A code-point offset into `text` as a UTF-16 index (what `slice` takes). */
export function utf16Index(text: string, codePoints: number): number {
  let index = 0
  let seen = 0
  for (const char of text) {
    if (seen === codePoints) break
    index += char.length
    seen += 1
  }
  return seen === codePoints ? index : text.length + (codePoints - seen)
}

function span(passage: Pick<Passage, "text" | "highlight" | "highlight_utf16">): Highlight | null {
  if (passage.highlight_utf16) return passage.highlight_utf16
  if (!passage.highlight) return null
  return { start: utf16Index(passage.text, passage.highlight.start), end: utf16Index(passage.text, passage.highlight.end) }
}

export function splitPassage(passage: Pick<Passage, "text" | "highlight" | "highlight_utf16">): PassageParts {
  const { text } = passage
  const raw = span(passage)
  if (!raw) return { before: text, match: "", after: "", clamped: false }
  const start = Math.min(Math.max(raw.start, 0), text.length)
  const end = Math.min(Math.max(raw.end, start), text.length)
  return {
    before: text.slice(0, start),
    match: text.slice(start, end),
    after: text.slice(end),
    clamped: start !== raw.start || end !== raw.end,
  }
}
