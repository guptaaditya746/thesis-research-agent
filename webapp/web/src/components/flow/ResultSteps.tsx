/**
 * The flow's last two steps, on the chosen engine run, built from the viewer's own parts and linked to its
 * pages: the evidence graph and the answer, in the form of the question's kind (with the baselines' answers on
 * the same corpus beside it). The scores are not a step: they stay on their own pages (/scores).
 */
import type { ReactNode } from "react"
import { Link } from "react-router"

import { isActiveJob, useCorpus, useEvRun, useEvRuns, useJobs, useRunGraph, type EvRunDetail } from "@/api/ev"
import { LabelBadge, SystemBadge } from "@/components/ev/bits"
import { EvidenceGraph } from "@/components/ev/EvidenceGraph"
import { EvidenceView } from "@/components/ev/EvidenceView"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { answerHeadline, effectAnswer } from "@/lib/ev"

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
  return <EvidenceGraph graph={graph.data} documents={run.documents} paperHref={(d) => `${runHref(run.id)}/papers/${encodeURIComponent(d)}`} />
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

/** A baseline's answer in one line, by the question's kind: the label of an effect answer, else the summary. */
function BaselineHeadline({ id }: { id: string }) {
  const run = useEvRun(id)
  const answer = run.data?.answer
  if (!answer) return null
  const effect = effectAnswer(answer)
  return effect ? <LabelBadge label={effect.label} /> : <span className="text-xs">{answerHeadline(answer)}</span>
}

function BaselineAnswers({ corpus }: { corpus: string | null | undefined }) {
  const runs = useEvRuns()
  const baselines = (runs.data ?? []).filter((r) => r.kind === "baseline" && r.corpus === corpus)
  if (!corpus) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Beside it: the baselines on {corpus}</CardTitle>
        <CardDescription>{baselines.length ? "Their answers in one line; open one for its details." : "None yet: start them in the run step."}</CardDescription>
      </CardHeader>
      {baselines.length > 0 && (
        <CardContent>
          <ul className="space-y-2">
            {baselines.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-2 text-sm">
                <SystemBadge system={b.system} />
                <BaselineHeadline id={b.id} />
                <Link to={runHref(b.id)} className="inline-flex min-h-6 items-center font-mono text-xs break-all underline">{b.id}</Link>
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
  return <EvidenceView run={run} expected={effectAnswer(run.answer) ? corpus.data?.answer?.label : null} />
}

export function AnswerStep({ flow }: { flow: Flow }) {
  return (
    <WithRun flow={flow}>
      {(run) => (
        <section className="space-y-4" aria-label="Answer">
          <p className="text-sm text-muted-foreground">
            The answer of <span className="font-mono">{run.id}</span>, in the form of the question's kind: the label and each study's
            direction, the names found, the claims against the data, or the best method kind. <Link to={runHref(run.id, "answer")} className="underline">Open in the run page</Link>
          </p>
          <Answer run={run} />
          <BaselineAnswers corpus={run.corpus} />
        </section>
      )}
    </WithRun>
  )
}
