/** Cells of the evidence table shared by the column sets: found by, the effect mark, a treatment or control value. */
import { MinusIcon, TrendingDownIcon, TrendingUpIcon } from "lucide-react"

import { DASH, num } from "@/lib/format"
import { extractorFamily, focusOn, signed, type EffectData, type EvidenceRow } from "@/lib/evidence"
import { cn } from "@/lib/utils"

import { SourceButton } from "./EvidenceTable"
import type { Opener } from "./useEvidenceTable"

/** Extractor families of the row's items ("regex", "llm", "gliner"), the full ids in the title. */
export function FoundByCell({ ids }: { ids: string[] }) {
  if (!ids.length) return <span className="text-muted-foreground">{DASH}</span>
  const families = [...new Set(ids.map(extractorFamily))]
  return (
    <span className="flex flex-wrap gap-1" title={ids.join("\n")}>
      {families.map((f) => <span key={f} className="rounded-sm border px-1 font-mono text-[11px]">{f}</span>)}
    </span>
  )
}

/**
 * The effect on one axis per metric (a forest-plot dot): left of the centre the control is better, right the
 * treatment; the arrow icon and the signed number say the same without the picture.
 */
export function EffectMark({ delta, direction, scale }: { delta: number | null; direction: string; scale: number }) {
  if (delta === null) return <span className="text-muted-foreground">{DASH}</span>
  const Icon = direction === "supports" ? TrendingUpIcon : direction === "contradicts" ? TrendingDownIcon : MinusIcon
  const x = 30 + (scale > 0 ? (delta / scale) * 26 : 0)
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <svg width="60" height="12" viewBox="0 0 60 12" aria-hidden="true" className="shrink-0">
        <line x1="2" x2="58" y1="6" y2="6" className="stroke-border" strokeWidth="1" />
        <line x1="30" x2="30" y1="1" y2="11" className="stroke-muted-foreground" strokeWidth="1" />
        <circle cx={x} cy="6" r="3.5" className={cn(direction === "supports" ? "fill-status-good" : direction === "contradicts" ? "fill-status-critical" : "fill-status-neutral")} />
      </svg>
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="font-mono tabular-nums">{signed(delta)}</span>
    </span>
  )
}

export function SideCell({ row, side, open }: { row: EvidenceRow<EffectData>; side: "treatment" | "control"; open: Opener }) {
  const s = row.data[side]
  if (!s) return <span className="text-muted-foreground">{DASH}</span>
  return (
    <SourceButton target={focusOn(row, s.measurement)} onOpen={open} label={`${row.key}: ${side} ${s.label ?? ""} ${num(s.value, 3)}, show in the paper`}>
      <span className="font-mono font-medium tabular-nums">{num(s.value, 3)}</span>
      <span className="block text-muted-foreground">{s.label ?? DASH}</span>
    </SourceButton>
  )
}

