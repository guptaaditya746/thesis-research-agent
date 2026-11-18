/** Box 4: the run. While it goes: "Running..." and the status; when it fails: the reason; when it is done: the
 * four rows (Find, Pull out, Combine, Answer), each with its count and a "Show" toggle. A fact of Pull out opens
 * its paper with the fact's spans marked. Done when the run is done. */
import { Button } from "@/components/ui/button"

import { usePlanResult } from "../plan/api"
import { runFailure, type SystemSteps } from "./api"
import { Box } from "./PickBox"
import { PaperPanel } from "./PaperPanel"

export type RowName = "find" | "pull" | "combine" | "answer"

function Row({ id, title, count, open, onToggle, children }: {
  id: RowName
  title: string
  count?: number
  open: boolean
  onToggle: (row: RowName) => void
  children: React.ReactNode
}) {
  return (
    <div role="group" aria-label={`${title} row`} className="rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{count === undefined ? title : `${title} ${count}`}</span>
        <Button variant="outline" size="sm" aria-expanded={open} onClick={() => onToggle(id)}>{open ? "Hide" : "Show"}</Button>
      </div>
      {open && <div className="mt-2 text-sm">{children}</div>}
    </div>
  )
}

export function FactButtons({ facts, onSelect }: { facts: number[]; onSelect: (n: number) => void }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {facts.map((n) => (
        <Button key={n} variant="outline" size="sm" className="h-6 px-2" aria-label={`Fact ${n}`} onClick={() => onSelect(n)}>{n}</Button>
      ))}
    </span>
  )
}

export function RunBox({ planId, run, selected, onSelect, opened, onToggle, steps }: {
  planId: string | null
  run: string | null
  selected: number | null
  onSelect: (n: number | null) => void
  opened: Record<RowName, boolean>
  onToggle: (row: RowName) => void
  steps: SystemSteps | undefined
}) {
  const result = usePlanResult(planId, run !== null)
  const status = result.data?.status ?? ""
  const failure = runFailure(result.data)
  const stepsFailed = steps?.status === "failed"
  const done = run !== null && failure === null && steps !== undefined && steps.status === "done" && status !== "running"
  const fact = steps?.pull.facts.find((f) => f.n === selected) ?? null

  return (
    <Box title="4. Run" open={run !== null}>
      {run !== null && failure === null && !stepsFailed && !done && (
        <p className="text-sm" role="status"><span>Running...</span>{status ? <span className="text-muted-foreground">{` ${status}`}</span> : null}</p>
      )}
      {failure !== null && <p role="alert" className="text-sm text-destructive">{failure}</p>}
      {stepsFailed && failure === null && <p role="alert" className="text-sm text-destructive">{`failed: ${steps?.error ?? "the run stopped"}`}</p>}
      {done && steps && (
        <div role="group" aria-label="Run rows" className="space-y-2">
          <Row id="find" title="Find" count={steps.find.count} open={opened.find} onToggle={onToggle}>
            <ul className="space-y-1">
              {steps.find.papers.map((p) => (
                <li key={p.paper}>
                  <span className="font-medium">{p.paper}</span>{" "}
                  <span>{p.kept ? "kept" : "dropped"}</span>{" "}
                  <span className="text-muted-foreground">{p.why}</span>
                </li>
              ))}
            </ul>
          </Row>
          <Row id="pull" title="Pull out" count={steps.pull.count} open={opened.pull} onToggle={onToggle}>
            {steps.pull.left_out > 0 && (
              <p className="mb-2 text-muted-foreground">{`${steps.pull.left_out} facts that bear on the plan were not given to the writer`}</p>
            )}
            <ul className="space-y-1">
              {steps.pull.facts.map((f) => (
                <li key={f.n}>
                  <button type="button" data-selected={f.n === selected ? "true" : "false"} onClick={() => onSelect(f.n)}
                    className="w-full rounded-md border px-2 py-1 text-left hover:bg-muted data-[selected=true]:bg-status-warning/40">
                    <span className="font-medium">{f.n}</span> <span className="text-muted-foreground">{`${f.paper}, ${f.type}`}</span> {f.text}
                  </button>
                </li>
              ))}
            </ul>
            {fact && run && <div className="mt-3"><PaperPanel rid={run} fact={fact} /></div>}
          </Row>
          <Row id="combine" title="Combine" count={steps.combine.count} open={opened.combine} onToggle={onToggle}>
            <p className="mb-2">{steps.combine.rule}</p>
            <ul className="space-y-1">
              {steps.combine.rows.map((r, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2"><span>{r.text}</span><FactButtons facts={r.facts} onSelect={onSelect} /></li>
              ))}
            </ul>
          </Row>
          <Row id="answer" title="Answer" count={steps.answer.lines.length} open={opened.answer} onToggle={onToggle}>
            <ul className="space-y-1">
              {steps.answer.lines.map((l, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2"><span>{l.text}</span><FactButtons facts={l.facts} onSelect={onSelect} /></li>
              ))}
            </ul>
          </Row>
        </div>
      )}
    </Box>
  )
}
