/**
 * A run's answer as evidence (the run page's Answer tab): the question and the answer first, a coverage bar
 * of the papers by lane (a lane's button filters the table), then the evidence table, one row per paper
 * grouped by verdict, and a click on a cell opens the source panel on that item's span in the paper. On a wide
 * screen the panel sits beside the table (the table stays in view); on a narrow one it is a sheet over it.
 *
 * The rows come from answer.json, the run's graph.json (labels, datasets, which extractor found each item)
 * and the run protocol's synthesis (the margin and which way each metric is better); see lib/evidence.ts.
 */
import { useMemo, useRef, useState, type ReactNode } from "react"

import { useRunGraph, useRunProtocol, type EffectAnswer, type EvRunDetail } from "@/api/ev"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { effectAnswer, ENGINE, type KindAnswer } from "@/lib/ev"
import { effectRows, EFFECT_LANES, indexGraph, laneCounts, type EvidenceRow, type Lane, type SourceTarget } from "@/lib/evidence"

import { AnswerPanel, BaselineEvidence } from "./AnswerPanel"
import { JsonBlock, LabelBadge, SystemBadge } from "./bits"
import { CoverageBar } from "./CoverageBar"
import { effectColumns } from "./EvidenceColumns"
import { ColumnsMenu, EvidenceTable } from "./EvidenceTable"
import { SourcePanel } from "./SourcePanel"
import { shownRows, useEvidenceTable, type EvidenceColumn } from "./useEvidenceTable"
import { useMediaQuery } from "./useMediaQuery"

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** "2 of 6 papers support, 1 contradicts, 3 are undetermined": the counts in one sentence. */
function effectSentence(answer: EffectAnswer, total: number): string {
  const c = (answer.counts ?? {}) as Record<string, number | undefined>
  const parts = [
    c.supporting ? `${c.supporting} support${c.supporting === 1 ? "s" : ""}` : null,
    c.contradicting ? `${c.contradicting} contradict${c.contradicting === 1 ? "s" : ""}` : null,
    c.neutral ? `${c.neutral} show${c.neutral === 1 ? "s" : ""} no effect` : null,
    c.undetermined ? `${c.undetermined} ${c.undetermined === 1 ? "is" : "are"} undetermined` : null,
    c.duplicates ? `${plural(c.duplicates, "duplicate")} not counted` : null,
  ].filter(Boolean)
  return `Of ${plural(total, "paper")}: ${parts.join(", ") || "none was used"}.`
}

function AnswerHeader({ system, question, answer, sentence, children }: {
  system: string
  question?: string | null
  answer: ReactNode
  sentence: string
  children?: ReactNode
}) {
  return (
    <section aria-label="Answer" className="space-y-2 rounded-lg border bg-card p-4">
      {question && <p className="text-sm text-muted-foreground">{question}</p>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-xl font-semibold tracking-tight">{answer}</span>
        <SystemBadge system={system} />
      </div>
      <p className="text-sm">{sentence}</p>
      {children}
    </section>
  )
}

interface KindView<T> {
  lanes: Lane[]
  rows: EvidenceRow<T>[]
  columns: EvidenceColumn<T>[]
  caption: string
  unit: string
  header: ReactNode
  after?: ReactNode
}

function Evidence<T>({ runId, view }: { runId: string; view: KindView<T> }) {
  const [laneFilter, setLaneFilter] = useState<string | null>(null)
  const [target, setTarget] = useState<SourceTarget | null>(null)
  const wide = useMediaQuery("(min-width: 1024px)")
  const phone = !useMediaQuery("(min-width: 640px)")
  const heading = useRef<HTMLHeadingElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  const rows = useMemo(() => (laneFilter ? view.rows.filter((r) => r.lane === laneFilter) : view.rows), [view.rows, laneFilter])
  const open = (t: SourceTarget | null) => {
    if (!t) return
    opener.current = document.activeElement as HTMLElement | null
    setTarget(t)
    // the docked panel takes focus on its heading, so a keyboard user lands on what opened
    if (wide) requestAnimationFrame(() => heading.current?.focus())
  }
  const close = () => {
    setTarget(null)
    requestAnimationFrame(() => opener.current?.focus())
  }
  const table = useEvidenceTable({ rows, columns: view.columns, onOpen: open, compact: phone || (wide && !!target) })
  const order = shownRows(table, view.lanes).filter((r) => r.target)
  const at = target ? order.findIndex((r) => r.key === target.key) : -1
  const step = (by: number) => {
    const next = order[at + by]?.target
    if (next) setTarget(next)
  }
  const panel = target && (
    <SourcePanel runId={runId} target={target} lane={view.lanes.find((l) => l.key === target.lane)} headingRef={heading}
      onFocus={(item) => setTarget({ ...target, focus: item })} onClose={wide ? close : null}
      onPrev={at > 0 ? () => step(-1) : undefined} onNext={at >= 0 && at < order.length - 1 ? () => step(1) : undefined}
      position={at >= 0 ? `${at + 1} of ${order.length}` : undefined} />
  )
  return (
    <div className="space-y-4">
      {view.header}
      <CoverageBar counts={laneCounts(view.rows, view.lanes)} active={laneFilter} onToggle={setLaneFilter} unit={view.unit}>
        <ColumnsMenu table={table} />
      </CoverageBar>
      <div className={target && wide ? "grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,42%)]" : undefined}>
        <EvidenceTable table={table} lanes={view.lanes} caption={view.caption} active={target?.key} />
        {wide && panel && (
          <aside aria-label={`Source: ${target.title}`} className="sticky top-4 max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-lg border bg-card p-4">
            {panel}
          </aside>
        )}
      </div>
      {!wide && (
        <Sheet open={!!target} onOpenChange={(o) => { if (!o) close() }}>
          <SheetContent className="w-full gap-0 overflow-y-auto p-4 pt-12 sm:max-w-xl">
            <SheetTitle className="sr-only">Source: {target?.title}</SheetTitle>
            <SheetDescription className="sr-only">The paper with this row's evidence marked.</SheetDescription>
            {panel}
          </SheetContent>
        </Sheet>
      )}
      {view.after}
    </div>
  )
}

function effectView(run: EvRunDetail, answer: EffectAnswer, expected: string | null | undefined, graph: ReturnType<typeof indexGraph>,
  synthesis: Parameters<typeof effectRows>[3]): KindView<unknown> {
  const engine = answer.system === ENGINE
  const rows = effectRows(answer, run.documents, graph, synthesis)
  return {
    lanes: EFFECT_LANES,
    rows: rows as EvidenceRow<unknown>[],
    columns: effectColumns(answer, rows, engine) as EvidenceColumn<unknown>[],
    caption: "Evidence per paper",
    unit: "papers",
    header: (
      <AnswerHeader system={answer.system} question={answer.question} sentence={effectSentence(answer, rows.length)}
        answer={<span className="inline-flex flex-wrap items-center gap-2">
          {answer.label}
          {expected && <LabelBadge label={`expected ${expected}`} correct={expected === answer.label} />}
        </span>}>
        {answer.answer_text && <blockquote className="border-l-2 pl-3 text-sm italic">{answer.answer_text}</blockquote>}
      </AnswerHeader>
    ),
    after: !engine && answer.retrieved ? <BaselineEvidence answer={answer} paperHref={(d) => `/runs/${encodeURIComponent(run.id)}/papers/${encodeURIComponent(d)}`} /> : undefined,
  }
}

export function EvidenceView({ run, expected }: { run: EvRunDetail; expected?: string | null }) {
  const engine = run.kind === "engine"
  const graph = useRunGraph(run.id, engine)
  const protocol = useRunProtocol(run.id, engine)
  const index = useMemo(() => indexGraph(graph.data), [graph.data])
  const synthesis = protocol.data?.protocol?.synthesis ?? null
  const answer = run.answer
  const effect = effectAnswer(answer)
  const view = useMemo(() => (effect ? effectView(run, effect, expected, index, synthesis) : null), [run, effect, expected, index, synthesis])
  if (!answer) return <p className="text-sm text-muted-foreground">No answer.json.</p>
  const paperHref = (d: string) => `/runs/${encodeURIComponent(run.id)}/papers/${encodeURIComponent(d)}`
  if (view) return <Evidence runId={run.id} view={view} />
  const known = answer as KindAnswer
  if (["inventory", "consistency", "best"].includes(known.kind ?? "")) return <AnswerPanel answer={answer} paperHref={paperHref} />
  return <JsonBlock value={answer} label={`answer of kind ${known.kind}`} />
}
