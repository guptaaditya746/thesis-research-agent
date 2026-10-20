/**
 * A paper's text with its spans marked: the backend cuts the text into segments (webapp/evfiles.py
 * `segments`, in code points), each listing the ids whose spans cover it, so this only draws. A marked
 * segment is underlined in the colour of the kind of thing it belongs to (`colorOf`: an evidence type, a
 * ground-truth role, a citation) and carries the ids in its title; clicking selects them (`onSelect`), and
 * the segments of the selected id are shaded so a span can be found from a list beside the text.
 */
import { memo, useCallback, useLayoutEffect, useRef } from "react"

import type { Segment as TextSegment } from "@/api/ev"
import { cn } from "@/lib/utils"

/**
 * One marked segment. Memoised on `active` rather than `selected`, so choosing an id re-renders only the
 * segments whose shading changes (a paper is thousands of segments); PaperText passes a stable `onSelect`.
 */
const Segment = memo(function Segment({ s, color, double, active, onSelect }: {
  s: TextSegment
  color: string
  double: boolean
  active: boolean
  onSelect?: (marks: string[]) => void
}) {
  const marks = s.marks ?? []
  return (
    <mark
      title={`${marks.join(", ")}${s.roles?.length ? ` (${s.roles.join(", ")})` : ""}`}
      aria-label={onSelect ? `${s.text} — ${marks.join(", ")}` : undefined}
      data-marks={marks.join(" ")}
      onClick={onSelect ? () => onSelect(marks) : undefined}
      onKeyDown={onSelect ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(marks) } } : undefined}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-pressed={onSelect ? active : undefined}
      className={cn("rounded-[2px] bg-transparent text-foreground underline decoration-2 underline-offset-[3px]", onSelect && "cursor-pointer",
        active && "bg-status-warning/40 ring-2 ring-status-warning-fg")}
      style={{ textDecorationColor: color, ...(double ? { textDecorationStyle: "double" } : {}) }}
    >
      {s.text}
    </mark>
  )
})

export function PaperText({ segments, colorOf, selected, onSelect, label }: {
  segments: TextSegment[]
  /** the mark colour of an id (null: not drawn) */
  colorOf: (mark: string) => string | null
  selected?: string | null
  onSelect?: (marks: string[]) => void
  label: string
}) {
  // Callers pass an inline `onSelect`; a stable wrapper keeps the memoised segments from re-rendering on it.
  const latest = useRef(onSelect)
  useLayoutEffect(() => { latest.current = onSelect })
  const select = useCallback((marks: string[]) => latest.current?.(marks), [])
  const selectable = onSelect ? select : undefined
  return (
    // A focusable region: the text scrolls, and keyboard users need to reach it to scroll it.
    <div role="region" tabIndex={0} aria-label={label}
      className="max-h-[70vh] overflow-auto rounded-md border bg-card p-4 font-serif text-sm leading-relaxed whitespace-pre-wrap focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
      {segments.map((s) => {
        const marks = s.marks ?? []
        const colors = marks.map(colorOf).filter((c): c is string => !!c)
        if (!colors.length) return <span key={s.start}>{s.text}</span>
        return <Segment key={s.start} s={s} color={colors[0]} double={colors.length > 1} active={!!selected && marks.includes(selected)} onSelect={selectable} />
      })}
    </div>
  )
}

export type LegendEntry = {
  label: string
  color: string
  /** the swatch's line: solid (a mark, a support edge), dashed or dotted (an edge kind) */
  line?: "solid" | "dashed" | "dotted"
}

/** The legend under a marked text or the graph: one line swatch per kind, with its label. */
export function MarkLegend({ entries, overlap = true, label = "Marks" }: {
  entries: LegendEntry[]
  /** the "double underline" note, which only means something under a paper's text */
  overlap?: boolean
  label?: string
}) {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label={label}>
      {entries.map((e) => (
        <li key={e.label} className="flex items-center gap-1.5">
          <span className="w-4 border-t-2" style={{ borderColor: e.color, borderTopStyle: e.line ?? "solid" }} aria-hidden="true" />
          {e.label}
        </li>
      ))}
      {overlap && <li>double underline: several marks overlap</li>}
    </ul>
  )
}
