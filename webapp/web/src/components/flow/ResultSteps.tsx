/**
 * The flow's last three steps, on the chosen engine run, built from the viewer's own parts and linked to its
 * pages: the evidence graph, the answer (with the baselines' answers on the same corpus beside it) and the
 * scores A/B/C (the run's report, the baselines beside the engine; comparisons on the corpus).
 */
import type { ReactNode } from "react"
import { Link, useNavigate } from "react-router"

import { isActiveJob, useCorpus, useEvRun, useEvRuns, useJobs, useReport, useRunGraph, useScores, useStartJob, type EvRunDetail } from "@/api/ev"
import { AnswerSummary, StudiesTable } from "@/components/ev/AnswerPanel"
import { LabelBadge, RowsTable, SystemBadge } from "@/components/ev/bits"
import { EvidenceGraph } from "@/components/ev/EvidenceGraph"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { evCell, synthesisSummary } from "@/lib/ev"
import { announceError, announceJob } from "@/lib/toasts"

import type { Flow } from "./flow"

const runHref = (id: string, tab?: string) => `/runs/${encodeURIComponent(id)}${tab ? `?tab=${tab}` : ""}`

function NeedsRun({ flow }: { flow: Flow }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Choose an engine run first</CardTitle>
        <CardDescription>Start one, or choose one on the corpus, in the <Link to={flow.href("run")} className="underline">run step</Link>.</CardDescription>
      </CardHeader>
    </Card>
  )
}

/** The chosen run, polled while a job writes it. */
function useChosenRun(flow: Flow) {
  const jobs = useJobs()
  const live = !!flow.run && (jobs.data ?? []).some((j) => isActiveJob(j) && j.refs.run === flow.run)
  return { run: useEvRun(flow.run ?? "", live), live }
}

function WithRun({ flow, children }: { flow: Flow; children: (run: EvRunDetail, live: boolean) => ReactNode }) {
  const { run, live } = useChosenRun(flow)
  if (!flow.run) return <NeedsRun flow={flow} />
  if (run.isPending) return <CardsSkeleton count={1} />
  if (run.isError) return <ErrorState error={run.error} title={live ? "The run has not written anything yet" : "Could not load the run"} />
  return <>{children(run.data, live)}</>
}

function Graph({ run, live }: { run: EvRunDetail; live: boolean }) {
  const graph = useRunGraph(run.id, run.kind === "engine", live)
  if (run.kind !== "engine") return <p className="text-sm text-muted-foreground">A baseline has no evidence graph.</p>
  if (graph.isPending) return <CardsSkeleton count={1} />
  if (graph.isError) return <p className="text-sm text-muted-foreground">{run.complete ? "No graph.json in this run." : "The engine writes graph.json when the run finishes."}</p>
  return <EvidenceGraph graph={graph.data} documents={run.documents} />
}

export function GraphStep({ flow }: { flow: Flow }) {
  return (
    <WithRun flow={flow}>
      {(run, live) => (
        <section className="space-y-2" aria-label="Evidence graph">
          <p className="text-sm text-muted-foreground">
            The merged items of <span className="font-mono">{run.id}</span> and how they connect{live ? " (the run is still going)" : ""}.{" "}
            <Link to={runHref(run.id, "graph")} className="underline">Open in the run page</Link>
          </p>
          <Graph run={run} live={live} />
        </section>
      )}
    </WithRun>
  )
}

function BaselineAnswers({ corpus }: { corpus: string | null | undefined }) {
  const runs = useEvRuns()
  const baselines = (runs.data ?? []).filter((r) => r.kind === "baseline" && r.corpus === corpus)
  if (!corpus) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Beside it: the baselines on {corpus}</CardTitle>
        <CardDescription>{baselines.length ? "Their labels; open one for its text, citations and stances." : "None yet: start them in the run step."}</CardDescription>
      </CardHeader>
      {baselines.length > 0 && (
        <CardContent>
          <ul className="space-y-2">
            {baselines.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-2 text-sm">
                <SystemBadge system={b.system} />
                <LabelBadge label={b.label} />
                <Link to={runHref(b.id)} className="font-mono text-xs underline">{b.id}</Link>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  )
}

function Answer({ run }: { run: EvRunDetail }) {
  const corpus = useCorpus(run.corpus ?? "")
  if (!run.answer) return <p className="text-sm text-muted-foreground">No answer.json yet: the engine writes it when the run finishes.</p>
  const paperHref = (d: string) => `${runHref(run.id)}/papers/${encodeURIComponent(d)}`
  return (
    <div className="space-y-4">
      <AnswerSummary answer={run.answer} expected={corpus.data?.answer?.label} />
      <StudiesTable answer={run.answer} paperHref={paperHref} funnel={run.funnel} strategy={run.strategy} />
    </div>
  )
}

export function AnswerStep({ flow }: { flow: Flow }) {
  return (
    <WithRun flow={flow}>
      {(run) => (
        <section className="space-y-4" aria-label="Answer">
          <p className="text-sm text-muted-foreground">
            The answer of <span className="font-mono">{run.id}</span>: the label from the protocol's decision table, each study's direction
            and reason. <Link to={runHref(run.id, "answer")} className="underline">Open in the run page</Link>
          </p>
          <Answer run={run} />
          <BaselineAnswers corpus={run.corpus} />
        </section>
      )}
    </WithRun>
  )
}

const C_COLUMNS = ["system", "label", "expected", "label_correct", "direction_accuracy", "completeness", "traceability"]

function Scores({ run }: { run: EvRunDetail }) {
  const scores = useScores()
  const has = (scores.data?.reports ?? []).some((r) => r.id === run.id)
  const report = useReport(has ? run.id : "")
  const score = useStartJob("score")
  const navigate = useNavigate()
  const compares = (scores.data?.compares ?? []).filter((c) => run.corpus && (c.id === `compare-${run.corpus}` || c.name === run.corpus))
  if (scores.isPending) return <CardsSkeleton count={1} />
  return (
    <div className="space-y-4">
      {!has ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Not scored yet.</span>
          <Button size="sm" disabled={!run.complete || score.isPending}
            onClick={() => score.mutate({ run: run.id }, { onSuccess: (job) => announceJob(job, navigate), onError: (e) => announceError("The score did not start", e) })}>
            Score this run
          </Button>
          {!run.complete && <span className="text-xs text-muted-foreground">once it has finished</span>}
        </div>
      ) : report.isPending ? <CardsSkeleton count={1} /> : report.isError ? <ErrorState error={report.error} /> : (
        <>
          <RowsTable caption="C. Synthesis per system" rows={synthesisSummary(report.data.report)} columns={C_COLUMNS}
            render={(c, v, row) => c === "system" ? <SystemBadge system={String(v)} />
              : c === "label" ? <LabelBadge label={String(v ?? "")} correct={row.label_correct as boolean | undefined} /> : evCell(v)} />
          <p className="text-sm">
            <Link to={`/scores/reports/${encodeURIComponent(run.id)}`} className="underline">The full report</Link>: A extraction per evidence type and level,
            B integration, C synthesis per level with 95 % intervals and the paired engine-minus-baseline difference.
          </p>
        </>
      )}
      {compares.length > 0 && (
        <p className="text-sm">Comparisons on this corpus: {compares.map((c) => <Link key={c.id} to={`/scores/compares/${encodeURIComponent(c.id)}`} className="mr-2 font-mono text-xs underline">{c.id}</Link>)}</p>
      )}
    </div>
  )
}

export function ScoresStep({ flow }: { flow: Flow }) {
  return (
    <WithRun flow={flow}>
      {(run) => (
        <section className="space-y-4" aria-label="Scores">
          <p className="text-sm text-muted-foreground">
            The scores of <span className="font-mono">{run.id}</span> against the corpus's ground truth, the baselines beside the engine.
          </p>
          {run.kind === "engine" ? <Scores run={run} /> : <p className="text-sm text-muted-foreground">A baseline is scored beside its engine run.</p>}
        </section>
      )}
    </WithRun>
  )
}
