/**
 * A paper's text with its spans marked: the backend cuts the text into segments (webapp/evfiles.py
 * `segments`, in code points), each listing the ids whose spans cover it, so this only draws. A marked
 * segment is underlined in the colour of the kind of thing it belongs to (`colorOf`: an evidence type, a
 * ground-truth role, a citation) and carries the ids in its title; clicking selects them (`onSelect`), and
 * the segments of the selected id are shaded so a span can be found from a list beside the text.
 */
import type { Segment } from "@/api/ev"
import { cn } from "@/lib/utils"

export function PaperText({ segments, colorOf, selected, onSelect, label }: {
  segments: Segment[]
  /** the mark colour of an id (null: not drawn) */
  colorOf: (mark: string) => string | null
  selected?: string | null
  onSelect?: (marks: string[]) => void
  label: string
}) {
  return (
    <div aria-label={label} className="max-h-[70vh] overflow-auto rounded-md border bg-card p-4 font-serif text-sm leading-relaxed whitespace-pre-wrap">
      {segments.map((s) => {
        const marks = s.marks ?? []
        const colors = marks.map(colorOf).filter((c): c is string => !!c)
        if (!colors.length) return <span key={s.start}>{s.text}</span>
        const active = !!selected && marks.includes(selected)
        return (
          <mark
            key={s.start}
            title={`${marks.join(", ")}${s.roles?.length ? ` (${s.roles.join(", ")})` : ""}`}
            data-marks={marks.join(" ")}
            onClick={onSelect ? () => onSelect(marks) : undefined}
            onKeyDown={onSelect ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(marks) } } : undefined}
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            className={cn("rounded-[2px] bg-transparent text-foreground underline decoration-2 underline-offset-[3px]", onSelect && "cursor-pointer",
              active && "bg-status-warning/30 ring-1 ring-status-warning/60")}
            style={{ textDecorationColor: colors[0], ...(colors.length > 1 ? { textDecorationStyle: "double" } : {}) }}
          >
            {s.text}
          </mark>
        )
      })}
    </div>
  )
}

/** The legend under a marked text: one swatch per kind, with its label. */
export function MarkLegend({ entries }: { entries: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label="Marks">
      {entries.map((e) => (
        <li key={e.label} className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded" style={{ background: e.color }} aria-hidden="true" />
          {e.label}
        </li>
      ))}
      <li>double underline: several marks overlap</li>
    </ul>
  )
}
