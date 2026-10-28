/**
 * The answer's coverage (PaperTrail's "claim coverage" bar): every paper of the run as a share of one bar,
 * split by lane (supports / contradicts / no effect / undetermined / duplicate / not in the answer). The bar
 * is a picture; the legend under it carries the same counts in words and is the control: a lane's button
 * filters the table to that lane (pressed again, or "all papers", shows every lane).
 */
import {
  ArrowDownRightIcon,
  ArrowUpRightIcon,
  CheckIcon,
  CircleHelpIcon,
  CircleIcon,
  CircleSlashIcon,
  CopyIcon,
  EqualIcon,
  TrophyIcon,
  XIcon,
  type LucideIcon,
} from "lucide-react"

import type { ReactNode } from "react"

import type { Lane, Tone } from "@/lib/evidence"
import { cn } from "@/lib/utils"

/** The fill of a lane: the status colours, the warning one in its darker shade (3:1 against the card). */
const TONE_FILL: Record<Tone, string> = {
  good: "var(--status-good)",
  critical: "var(--status-critical)",
  neutral: "var(--status-neutral)",
  warning: "var(--status-warning-fg)",
}
const TONE_TEXT: Record<Tone, string> = {
  good: "text-status-good",
  critical: "text-status-critical",
  neutral: "text-muted-foreground",
  warning: "text-status-warning-fg",
}

const LANE_ICON: Record<string, LucideIcon> = {
  supports: ArrowUpRightIcon,
  contradicts: ArrowDownRightIcon,
  neutral: EqualIcon,
  undetermined: CircleHelpIcon,
  duplicate: CopyIcon,
  absent: CircleSlashIcon,
  agrees: CheckIcon,
  disagrees: XIcon,
  winner: TrophyIcon,
  tie: EqualIcon,
  found: CheckIcon,
}

export function LaneIcon({ lane, className }: { lane: Lane; className?: string }) {
  const Icon = LANE_ICON[lane.key] ?? CircleIcon
  return <Icon aria-hidden="true" className={cn("size-3.5 shrink-0", TONE_TEXT[lane.tone], className)} />
}

/** A muted lane is hatched, so it differs from its neighbour by more than its colour. */
const fill = (lane: Lane) =>
  lane.muted
    ? `repeating-linear-gradient(135deg, ${TONE_FILL[lane.tone]} 0 3px, transparent 3px 6px)`
    : TONE_FILL[lane.tone]

export function CoverageBar({ counts, active, onToggle, unit = "papers", children }: {
  counts: { lane: Lane; count: number }[]
  active: string | null
  onToggle: (lane: string | null) => void
  unit?: string
  /** controls at the end of the legend row (the columns menu) */
  children?: ReactNode
}) {
  const total = counts.reduce((n, c) => n + c.count, 0)
  const shown = counts.filter((c) => c.count > 0)
  if (!total) return children ? <div className="flex justify-end">{children}</div> : null
  return (
    <div className="space-y-2">
      {/* the picture; the legend below says the same in words and is what the keyboard reaches */}
      <div className="flex h-3 w-full overflow-hidden rounded-sm border bg-muted" aria-hidden="true">
        {shown.map(({ lane, count }) => (
          <div key={lane.key} onClick={() => onToggle(active === lane.key ? null : lane.key)} title={`${lane.label}: ${count}`}
            className={cn("h-full cursor-pointer border-r border-card last:border-r-0", active && active !== lane.key && "opacity-30")}
            style={{ width: `${(count / total) * 100}%`, background: fill(lane) }} />
        ))}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-2">
      <ul className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 gap-y-1 text-sm" aria-label={`${total} ${unit} by lane`}>
        {shown.map(({ lane, count }) => (
          <li key={lane.key}>
            <button type="button" aria-pressed={active === lane.key} onClick={() => onToggle(active === lane.key ? null : lane.key)}
              title={lane.hint}
              className={cn("inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-md border border-transparent px-2 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                active === lane.key && "border-foreground bg-muted")}>
              <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: fill(lane) }} aria-hidden="true" />
              <LaneIcon lane={lane} />
              <span>{lane.label}</span>
              <span className="font-mono tabular-nums">{count}</span>
            </button>
          </li>
        ))}
        {active && (
          <li>
            <button type="button" onClick={() => onToggle(null)}
              className="min-h-8 cursor-pointer rounded-md px-2 text-muted-foreground underline underline-offset-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
              all {unit}
            </button>
          </li>
        )}
      </ul>
      {children}
      </div>
    </div>
  )
}
