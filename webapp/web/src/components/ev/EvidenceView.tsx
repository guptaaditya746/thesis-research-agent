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
import { Link } from "react-router"

import {
  useRunGraph,
  useRunProtocol,
  type BestAnswer,
  type ConsistencyAnswer,
  type EffectAnswer,
  type EvRunDetail,
  type InventoryAnswer,
  type Protocol,
} from "@/api/ev"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { effectAnswer, ENGINE, type KindAnswer } from "@/lib/ev"
import {
  BEST_LANES,
  bestRows,
  CONSISTENCY_LANES,
  consistencyRows,
  EFFECT_LANES,
  effectRows,
  indexGraph,
  INVENTORY_LANES,
  inventoryMissing,
  inventoryRows,
  laneCounts,
  type EvidenceRow,
  type Lane,
  type SourceTarget,
} from "@/lib/evidence"

import { BaselineEvidence } from "./AnswerPanel"
import { JsonBlock, LabelBadge, SystemBadge } from "./bits"
import { CoverageBar } from "./CoverageBar"
import { bestColumns, bestFooter, consistencyColumns, effectColumns, inventoryColumns } from "./EvidenceColumns"
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
  footer?: Record<string, string>
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
  const compact = phone || (wide && !!target)
  const table = useEvidenceTable({ rows, columns: view.columns, onOpen: open, compact, phone })
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
      <p className="sr-only" aria-live="polite">
        {laneFilter ? `Showing ${rows.length} of ${view.rows.length} ${view.unit}: ${view.lanes.find((l) => l.key === laneFilter)?.label}` : ""}
      </p>
      <div className={target && wide ? "grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,42%)]" : undefined}>
        <EvidenceTable table={table} lanes={view.lanes} caption={view.caption} active={target?.key} footer={view.footer} compact={compact} />
        {wide && panel && (
          <aside aria-label={`Source: ${target.title}`} onKeyDown={(e) => { if (e.key === "Escape") close() }}
            className="sticky top-4 max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-lg border bg-card p-4">
            {panel}
          </aside>
        )}
      </div>
      {!wide && (
        <Sheet open={!!target} onOpenChange={(o) => { if (!o) close() }}>
          <SheetContent className="w-full gap-0 overflow-y-auto p-4 pt-12 motion-reduce:animate-none! motion-reduce:transition-none! sm:max-w-xl">
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

type Graph = ReturnType<typeof indexGraph>
const erase = <T,>(v: { rows: EvidenceRow<T>[]; columns: EvidenceColumn<T>[] }) =>
  ({ rows: v.rows as EvidenceRow<unknown>[], columns: v.columns as EvidenceColumn<unknown>[] })

function effectView(run: EvRunDetail, answer: EffectAnswer, expected: string | null | undefined, graph: Graph, protocol: Protocol | null): KindView<unknown> {
  const engine = answer.system === ENGINE
  const rows = effectRows(answer, run.documents, graph, protocol?.synthesis)
  return {
    lanes: EFFECT_LANES,
    ...erase({ rows, columns: effectColumns(answer, rows, engine) }),
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

function inventoryView(run: EvRunDetail, answer: InventoryAnswer, graph: Graph): KindView<unknown> {
  const rows = inventoryRows(answer, graph)
  const missing = inventoryMissing(answer, run.documents)
  const named = run.documents.length - missing.length
  return {
    lanes: INVENTORY_LANES,
    ...erase({ rows, columns: inventoryColumns(answer) }),
    caption: "Inventory",
    unit: "names",
    header: (
      <AnswerHeader system={answer.system} question={`Which ${answer.target ?? "item"}s do the papers report?`}
        answer={plural(answer.entries.length, `distinct ${answer.target ?? "item"} name`)}
        sentence={`Named in ${named} of ${plural(run.documents.length, "paper")}${missing.length ? `; ${plural(missing.length, "paper")} name${missing.length === 1 ? "s" : ""} none` : ""}.`} />
    ),
    after: missing.length > 0 && (
      <section aria-label="Papers that name none" className="space-y-1 text-sm">
        <h4 className="text-xs font-medium text-muted-foreground">Papers that name none</h4>
        <ul className="flex flex-wrap gap-1">{missing.map((d) => <li key={d}><PaperLink runId={run.id} doc={d} /></li>)}</ul>
      </section>
    ),
  }
}

function consistencyView(run: EvRunDetail, answer: ConsistencyAnswer, graph: Graph): KindView<unknown> {
  const rows = consistencyRows(answer, run.documents, graph)
  const und = answer.undetermined.length
  return {
    lanes: CONSISTENCY_LANES,
    ...erase({ rows, columns: consistencyColumns(answer) }),
    caption: "Claims against numbers",
    unit: "papers",
    header: (
      <AnswerHeader system={answer.system} question="Do the authors' claims agree with their own numbers?"
        answer={`${answer.agreeing.length} agree, ${answer.disagreeing.length} disagree`}
        sentence={`Of ${plural(rows.length, "paper")}${answer.metric ? `, on ${answer.metric}` : ""}: ${answer.agreeing.length} agree, ${answer.disagreeing.length} disagree, ${und} ${und === 1 ? "is" : "are"} undetermined.`} />
    ),
  }
}

function bestView(run: EvRunDetail, answer: BestAnswer, graph: Graph, protocol: Protocol | null): KindView<unknown> {
  const kinds = protocol?.best?.kinds ?? null
  const rows = bestRows(answer, run.documents, graph, kinds)
  const wins = Object.entries(answer.wins).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k} ${n}`).join(", ")
  return {
    lanes: BEST_LANES,
    ...erase({ rows, columns: bestColumns(rows, kinds ? Object.keys(kinds) : undefined) }),
    caption: "Winner per paper",
    unit: "papers",
    footer: bestFooter(answer),
    header: (
      <AnswerHeader system={answer.system} question={`Which method kind is best${answer.metric ? ` on ${answer.metric}` : ""}?`}
        answer={answer.winner ? `best: ${answer.winner}` : answer.tied.length ? `tie: ${answer.tied.join(", ")}` : "no winner"}
        sentence={`Papers won per kind: ${wins || "none"} (of ${plural(rows.length, "paper")}).`} />
    ),
  }
}

/** A paper with no row: its page (the funnel and every item found in it). */
function PaperLink({ runId, doc }: { runId: string; doc: string }) {
  return (
    <Link to={`/runs/${encodeURIComponent(runId)}/papers/${encodeURIComponent(doc)}`}
      className="inline-flex min-h-6 items-center rounded-md border px-1.5 font-mono text-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
      {doc}
    </Link>
  )
}

export function EvidenceView({ run, expected }: { run: EvRunDetail; expected?: string | null }) {
  const engine = run.kind === "engine"
  const graph = useRunGraph(run.id, engine)
  const protocol = useRunProtocol(run.id, engine)
  const index = useMemo(() => indexGraph(graph.data), [graph.data])
  const spec = protocol.data?.protocol ?? null
  const answer = run.answer
  const view = useMemo((): KindView<unknown> | null => {
    if (!answer) return null
    const effect = effectAnswer(answer)
    if (effect) return effectView(run, effect, expected, index, spec)
    const known = answer as KindAnswer
    switch (known.kind) {
      case "inventory": return inventoryView(run, known, index)
      case "consistency": return consistencyView(run, known, index)
      case "best": return bestView(run, known, index, spec)
      default: return null
    }
  }, [run, answer, expected, index, spec])
  if (!answer) return <p className="text-sm text-muted-foreground">No answer.json.</p>
  if (view) return <Evidence runId={run.id} view={view} />
  return <JsonBlock value={answer} label={`answer of kind ${(answer as { kind?: string }).kind}`} />
}
