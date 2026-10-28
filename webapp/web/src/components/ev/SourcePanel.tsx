/**
 * The source panel beside the evidence table (SciDaSynth's panel D): one row's paper with only that row's
 * items marked, scrolled to the clicked one. On top, the row's "why" chain (treatment, control, metric, the
 * rule that gave the verdict, the author's claim), each link naming the extractors that found it and, when it
 * rests on an item, a button that scrolls the text to its span. A row with no item (undetermined, a paper
 * the answer left out) marks every item the engine found in the paper, so the gap can be seen.
 */
import { ChevronLeftIcon, ChevronRightIcon, ExternalLinkIcon, XIcon } from "lucide-react"
import { useEffect, useMemo, useRef } from "react"
import { Link } from "react-router"

import { useRunPaper } from "@/api/ev"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/states"
import { extractorName, TYPE_COLOR, typeLabel } from "@/lib/ev"
import type { Lane, SourceTarget } from "@/lib/evidence"
import { cn } from "@/lib/utils"

import { LaneIcon } from "./CoverageBar"
import { MarkLegend, PaperText } from "./PaperText"
import { useReducedMotion } from "./useMediaQuery"

const CITED = "var(--chart-2)"

export function FoundBy({ ids }: { ids: string[] | undefined }) {
  if (!ids?.length) return null
  return (
    <span className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
      found by
      {ids.map((id) => (
        <span key={id} title={id} className="rounded-sm border bg-background px-1 font-mono text-foreground">{extractorName(id)}</span>
      ))}
    </span>
  )
}

export function SourcePanel({ runId, target, lane, onFocus, onClose, onPrev, onNext, position, headingRef }: {
  runId: string
  target: SourceTarget
  lane?: Lane
  onFocus: (item: string) => void
  /** null: the container closes it (the sheet's own close button) */
  onClose: (() => void) | null
  onPrev?: () => void
  onNext?: () => void
  /** "2 of 6" */
  position?: string
  headingRef?: React.Ref<HTMLHeadingElement>
}) {
  const paper = useRunPaper(runId, target.document)
  const reduced = useReducedMotion()
  const textRef = useRef<HTMLDivElement>(null)
  const types = useMemo(() => new Map((paper.data?.items ?? []).map((i) => [i.item_id, i.evidence_type])), [paper.data])
  // the row's items that are in this paper; none: every item of the paper, so an empty row still shows what was found
  const marked = useMemo(() => {
    const own = target.items.filter((i) => types.has(i))
    return new Set(own.length ? own : types.keys())
  }, [target.items, types])
  const fallback = !target.items.some((i) => types.has(i))
  const focus = target.focus && marked.has(target.focus) ? target.focus : null

  // Scroll the text box (not the page) so the focused span sits in its upper third.
  useEffect(() => {
    const box = textRef.current?.querySelector<HTMLElement>("[role=region]")
    if (!box || !focus) return
    const mark = [...box.querySelectorAll<HTMLElement>("mark")].find((m) => (m.dataset.marks ?? "").split(" ").includes(focus))
    if (!mark) return
    const top = box.scrollTop + mark.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3
    box.scrollTo({ top: Math.max(0, top), behavior: reduced ? "auto" : "smooth" })
  }, [focus, paper.data, reduced])

  const presentTypes = [...new Set([...marked].map((m) => types.get(m)).filter((t): t is NonNullable<typeof t> => !!t))]
  const hasCited = target.cited && (paper.data?.segments ?? []).some((s) => s.marks?.some((m) => m.startsWith("cited:")))
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <h3 ref={headingRef} tabIndex={-1} className="font-mono text-base font-semibold focus-visible:outline-none">{target.title}</h3>
          {lane && (
            <p className="text-xs">
              <LaneIcon lane={lane} className="mr-1 inline align-[-2px]" />{lane.label}
              <span className="text-muted-foreground"> · {lane.hint}</span>
            </p>
          )}
        </div>
        <div className="flex items-center gap-1">
          {position && <span className="mr-1 text-xs text-muted-foreground tabular-nums">{position}</span>}
          {onPrev && <Button size="icon-sm" variant="outline" onClick={onPrev} aria-label="Previous paper"><ChevronLeftIcon /></Button>}
          {onNext && <Button size="icon-sm" variant="outline" onClick={onNext} aria-label="Next paper"><ChevronRightIcon /></Button>}
          {onClose && <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close the source panel"><XIcon /></Button>}
        </div>
      </div>

      {target.why.length > 0 && (
        <ol className="space-y-1" aria-label="Why this verdict">
          {target.why.map((step, n) => {
            const on = !!step.item && marked.has(step.item)
            return (
              <li key={n} className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-x-2 text-sm">
                <span className="pt-0.5 text-xs text-muted-foreground">{step.role}</span>
                <span className="min-w-0 space-y-0.5">
                  {on ? (
                    <button type="button" onClick={() => onFocus(step.item!)} aria-pressed={focus === step.item}
                      className={cn("min-h-6 cursor-pointer rounded-sm px-1 text-left underline decoration-2 underline-offset-[3px] hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                        focus === step.item && "bg-status-warning/30")}
                      style={{ textDecorationColor: TYPE_COLOR[types.get(step.item!) ?? ""] }}>
                      {step.text}
                    </button>
                  ) : <span className="block break-words">{step.text}</span>}
                  <FoundBy ids={step.foundBy} />
                </span>
              </li>
            )
          })}
        </ol>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <MarkLegend overlap={false} entries={[...presentTypes.map((t) => ({ label: typeLabel(t), color: TYPE_COLOR[t] })), ...(hasCited ? [{ label: "cited passage", color: CITED }] : [])]} />
        <Link to={`/runs/${encodeURIComponent(runId)}/papers/${encodeURIComponent(target.document)}`}
          className="inline-flex items-center gap-1 text-xs underline underline-offset-2">
          paper page with its funnel and calls<ExternalLinkIcon aria-hidden="true" className="size-3" />
        </Link>
      </div>
      {fallback && types.size > 0 && (
        <p className="text-xs text-muted-foreground">No item of this row is in the paper; every item the engine found in it is marked.</p>
      )}
      <div ref={textRef}>
        {paper.isPending ? <Skeleton className="h-64 w-full" /> : paper.isError ? (
          <ErrorState error={paper.error} onRetry={() => void paper.refetch()} />
        ) : paper.data.text === null || paper.data.text === undefined ? (
          <p className="text-sm text-muted-foreground">The run's corpus is not under the corpora root, so its text cannot be shown.</p>
        ) : (
          <PaperText label={`Text of ${target.document}`} segments={paper.data.segments} selected={focus} className="max-h-[60vh]"
            colorOf={(m) => (m.startsWith("cited:") ? (target.cited ? CITED : null) : marked.has(m) ? TYPE_COLOR[types.get(m) ?? ""] ?? null : null)}
            onSelect={(marks) => { const hit = marks.find((m) => marked.has(m)); if (hit) onFocus(hit) }} />
        )}
      </div>
    </div>
  )
}
