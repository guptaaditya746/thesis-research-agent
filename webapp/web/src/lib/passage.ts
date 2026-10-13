/**
 * The quote inside a corpus passage (claim walk, last link).
 *
 * GET /api/corpus/{paper} returns a window of the file: `text` starts at file offset `offset`
 * and `highlight` is the claim's anchor in file offsets (agent/anchor.py raw offsets). The
 * highlight is clamped to the window, so a stale anchor still renders instead of throwing.
 */
import type { Passage } from "@/api/types"

export interface PassageParts {
  before: string
  match: string
  after: string
  /** the highlight fell (partly) outside the window */
  clamped: boolean
}

export function splitPassage(passage: Pick<Passage, "text" | "highlight" | "offset">): PassageParts {
  const { text, highlight, offset } = passage
  const rawStart = highlight.start - offset
  const rawEnd = highlight.end - offset
  const start = Math.min(Math.max(rawStart, 0), text.length)
  const end = Math.min(Math.max(rawEnd, start), text.length)
  return {
    before: text.slice(0, start),
    match: text.slice(start, end),
    after: text.slice(end),
    clamped: start !== rawStart || end !== rawEnd,
  }
}
