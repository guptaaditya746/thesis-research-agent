/**
 * The flow's run step: with the chosen protocol and corpus, start the engine (`evidence run`: regex-only or the
 * cascade, all or gaps, the model), the RAG baseline (global top 8 passages) and the agent baseline on the same
 * corpus, then score each engine run (`evaluate score`, with the corpus's baselines beside it) and compare
 * them (`evaluate compare`). While a job runs, its log tails here and the runs and the chosen run poll, so the
 * run page fills in as the engine writes it.
 */
import { BarChart3Icon, BotIcon, GitCompareIcon, PlayIcon, SearchIcon } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import {
  isActiveJob,
  useCorpora,
  useEvConfig,
  useEvRun,
  useEvRuns,
  useJobs,
  useRunGroup,
  useScores,
  useStartJob,
  type EvRunSummary,
  type Job,
  type RunRequest,
} from "@/api/ev"
import { ErrorCallsBadge } from "@/components/badges"
import { KeyValues, LabelBadge, SystemBadge } from "@/components/ev/bits"
import { JobPanel } from "@/components/jobs/JobPanel"
import { TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { answerHeadline, effectAnswer } from "@/lib/ev"
import { baselineName, isName } from "@/lib/jobs"
import { announceError, announceJob } from "@/lib/toasts"

import { protocolLabel, type Flow } from "./flow"
import { TYPED_FLOW } from "./QuestionStep"

type Extractors = "regex-only" | "cascade" | "agentic"

function RunForm({ flow, corpus, existing }: { flow: Flow; corpus: string; existing: Set<string> }) {
  const config = useEvConfig()
  const q = flow.question
  const agenticOffered = !!q.agentic_protocol && flow.protocol?.source === "repo" && flow.protocol.name === q.protocol
  const [extractors, setExtractors] = useState<Extractors>("cascade")
  const [strategy, setStrategy] = useState<"all" | "gaps">("gaps")
  const [model, setModel] = useState("")
  const [name, setName] = useState("")
  const [retry, setRetry] = useState(false)
  const start = useStartJob("run")
  const navigate = useNavigate()
  const protocol = extractors === "agentic" && q.agentic_protocol ? { source: "repo" as const, name: q.agentic_protocol } : flow.protocol
  const selected = { extractors: extractors === "regex-only" ? "regex-only" as const : "cascade" as const, strategy: extractors === "regex-only" ? "all" as const : strategy }
  const groupName = useRunGroup(protocol ?? { source: "repo", name: "" }, selected.extractors, selected.strategy)
  if (!protocol) return null
  const body: RunRequest = {
    corpus, protocol, ...selected, model: model || config.data?.default_model || "orch-model",
    group: null, name: name || null, retry_errors: retry,
  }
  const group = groupName.data?.group
  const id = group ? `${group}~${name || corpus}` : null
  const taken = id !== null && existing.has(id)
  const ok = (!name || isName(name)) && !taken
  return (
    <form className="space-y-3" aria-label="Start the engine" onSubmit={(e) => {
      e.preventDefault()
      start.mutate(body, {
        onSuccess: (job) => { announceJob(job, navigate); flow.set({ run: job.refs.run ?? id ?? null }) },
        onError: (err) => announceError("The run did not start", err),
      })
    }}>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="run-extractors">Extractors</Label>
          <Select value={extractors} onValueChange={(v) => setExtractors(v as Extractors)}>
            <SelectTrigger id="run-extractors" className="w-64" aria-label="Extractors"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="regex-only">regex only (no model)</SelectItem>
              <SelectItem value="cascade">cascade: regex, then the LLM extractor</SelectItem>
              {agenticOffered && <SelectItem value="agentic">cascade with the agentic extractor last</SelectItem>}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="run-strategy">Strategy</Label>
          <Select value={extractors === "regex-only" ? "all" : strategy} onValueChange={(v) => setStrategy(v as "all" | "gaps")} disabled={extractors === "regex-only"}>
            <SelectTrigger id="run-strategy" className="w-56" aria-label="Strategy"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">all: every extractor on every paper</SelectItem>
              <SelectItem value="gaps">gaps: the funnel, escalate only the gaps</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="run-model">Model</Label>
          <Input id="run-model" className="w-40 font-mono" placeholder={config.data?.default_model ?? "orch-model"} value={model} onChange={(e) => setModel(e.target.value)} disabled={extractors === "regex-only"} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="run-name">Run name</Label>
          <Input id="run-name" className="w-56 font-mono" placeholder={corpus} value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!ok} aria-describedby={ok ? undefined : "run-name-error"} />
          {/* under the field, not in the note below the row: that is where the eye is when Start is off */}
          {!ok && <p id="run-name-error" className="w-56 text-xs text-destructive">{taken ? "That run exists: give this one a name of its own." : "Letters, digits, . _ -; starting with a letter or digit."}</p>}
        </div>
        <div className="flex items-center gap-2 pb-2">
          <Switch id="run-retry" checked={retry} onCheckedChange={setRetry} aria-label="Retry errors" />
          <Label htmlFor="run-retry" title="--retry-errors: run cached error results again instead of taking them from the record cache">retry errors</Label>
        </div>
        <Button type="submit" disabled={!ok || start.isPending}>
          <PlayIcon data-icon="inline-start" />
          Start run
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Writes <span className="font-mono">runs/{group ?? "…"}/{name || corpus}</span> with protocol {protocol.name}. {extractors === "regex-only" ? "No model: it runs beside other jobs." : "Calls the model: model jobs run one at a time, the same model for every extractor and both baselines."}
        {config.data && !config.data.llm_key_set && extractors !== "regex-only" && <strong className="block text-status-critical">The server has no $LITELLM_MASTER_KEY: model jobs are refused. Start it with llm-setup's .env sourced (README "Web app").</strong>}
      </p>
    </form>
  )
}

function Baselines({ corpus, question, runs, busy }: { corpus: string; question: string; runs: EvRunSummary[]; busy: Job[] }) {
  const rag = useStartJob("rag-baseline")
  const agent = useStartJob("agent-baseline")
  const config = useEvConfig()
  const navigate = useNavigate()
  if (question === TYPED_FLOW) {
    return <p className="text-sm text-muted-foreground">The baselines answer the questions of the list only; this question was typed.</p>
  }
  const name = baselineName(corpus, question)
  const has = (system: string) => runs.some((r) => r.id === `${system}~${name}`)
  const running = (system: string) => busy.some((j) => j.refs.run === `${system}~${name}`)
  const model = config.data?.default_model ?? "orch-model"
  const done = { onSuccess: (job: Job) => announceJob(job, navigate), onError: (e: unknown) => announceError("The baseline did not start", e) }
  // a disabled button says why: the answer is on disk (with a link to it) or its job is running
  const state = (system: string) => (running(system) ? "running…" : has(system) ? "done" : null)
  const open = (system: string) => has(system) && (
    <Link to={`/runs/${encodeURIComponent(`${system}~${name}`)}`} className="text-xs underline" aria-label={`Open ${system}~${name}`}>open</Link>
  )
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="outline" disabled={!!state("rag-baseline") || rag.isPending}
        onClick={() => rag.mutate({ corpus, question, model, retrieval: "global", k: 8 }, done)}>
        <SearchIcon data-icon="inline-start" />
        {state("rag-baseline") ? `RAG baseline: ${state("rag-baseline")}` : "RAG baseline (global top 8)"}
      </Button>
      {open("rag-baseline")}
      <Button variant="outline" disabled={!!state("agent-baseline") || agent.isPending}
        onClick={() => agent.mutate({ corpus, question, model }, done)}>
        <BotIcon data-icon="inline-start" />
        {state("agent-baseline") ? `Agent baseline: ${state("agent-baseline")}` : "Agent baseline"}
      </Button>
      {open("agent-baseline")}
      <span className="text-xs text-muted-foreground">
        Plain retrieve-then-answer and the research agent with the question only, on {model}; each writes runs/&lt;baseline&gt;/{name}.
        {config.data && !config.data.agent_root ? " No $AGENT_ROOT: the agent baseline runs without the pinned toolchain." : ""}
      </span>
    </div>
  )
}

function SelectedRun({ id, live }: { id: string; live: boolean }) {
  const run = useEvRun(id, live)
  if (run.isPending) return <p className="text-sm text-muted-foreground">Waiting for the run to write its first files…</p>
  if (run.isError) return <p className="text-sm text-muted-foreground">{live ? "The run has not written anything yet." : "No such run."}</p>
  const r = run.data
  const effect = effectAnswer(r.answer)
  return (
    <KeyValues items={[
      ["state", r.complete ? "complete" : live ? "running: events and calls so far" : "incomplete (crashed, or still running elsewhere)"],
      ["papers", String(r.documents.length)],
      ["answer", r.answer ? (effect ? <LabelBadge key="l" label={effect.label} /> : answerHeadline(r.answer)) : "—"],
      ["open", <Link key="o" to={`/runs/${encodeURIComponent(id)}`} className="underline">the run page</Link>],
    ]} />
  )
}

export function RunStep({ flow }: { flow: Flow }) {
  const corpus = flow.corpus
  const jobs = useJobs()
  const active = (jobs.data ?? []).filter(isActiveJob)
  const corpora = useCorpora()
  const runs = useEvRuns(active.length > 0)
  const scores = useScores(active.some((j) => j.kind === "score" || j.kind === "compare"))
  const compare = useStartJob("compare")
  const score = useStartJob("score")
  const navigate = useNavigate()
  if (!flow.protocol || !corpus) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Choose a protocol and a corpus first</CardTitle>
          <CardDescription>
            Protocol: {protocolLabel(flow.protocol)} (<Link to={flow.href("protocol")} className="underline">protocol step</Link>). Corpus:{" "}
            {corpus ?? "none"} (<Link to={flow.href("corpus")} className="underline">corpus step</Link>).
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }
  const built = corpora.data?.some((c) => c.name === corpus)
  const mine = (runs.data ?? []).filter((r) => r.corpus === corpus || (!r.corpus && r.name === corpus) || active.some((j) => j.refs.run === r.id && j.refs.corpus === corpus))
  const ids = new Set(mine.map((r) => r.id))
  const myJobs = active.filter((j) => j.refs.corpus === corpus || ids.has(j.refs.run ?? "") || ids.has(j.refs.score ?? "") || j.refs.score === `compare-${corpus}`)
  const reports = new Set((scores.data?.reports ?? []).map((r) => r.id))
  const scored = mine.filter((r) => r.kind === "engine" && reports.has(r.id))
  const done = { onSuccess: (job: Job) => announceJob(job, navigate), onError: (e: unknown) => announceError("The job did not start", e) }
  const liveRun = !!flow.run && active.some((j) => j.refs.run === flow.run)
  return (
    <div className="space-y-6">
      {myJobs.length > 0 && (
        <section className="space-y-2" aria-label="Jobs on this corpus">
          {myJobs.map((j) => <JobPanel key={j.id} job={j} compact />)}
        </section>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Engine</CardTitle>
          <CardDescription>
            {protocolLabel(flow.protocol)} on <Link to={`/corpora/${encodeURIComponent(corpus)}`} className="font-mono underline">{corpus}</Link>
            {corpora.data && !built ? " — not built yet (its build job may still be running)." : "."}
          </CardDescription>
        </CardHeader>
        <CardContent><RunForm flow={flow} corpus={corpus} existing={new Set((runs.data ?? []).map((r) => r.id))} /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Baselines on the same corpus</CardTitle></CardHeader>
        <CardContent><Baselines corpus={corpus} question={flow.question.id} runs={mine} busy={myJobs} /></CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Runs on {corpus}</CardTitle>
          <CardDescription>Choose the engine run whose graph, answer and scores the next steps show; score a finished run, then compare.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {runs.isPending ? <TableSkeleton rows={3} /> : mine.length === 0 ? <p className="text-sm text-muted-foreground">No runs on this corpus yet.</p> : (
            <div className="overflow-auto rounded-md border">
              <Table aria-label="Runs on the corpus">
                <TableHeader>
                  <TableRow>{["run", "system", "state", "label", ""].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}</TableRow>
                </TableHeader>
                <TableBody>
                  {mine.map((r) => {
                    const running = active.some((j) => j.refs.run === r.id)
                    const scoring = active.some((j) => j.kind === "score" && j.refs.score === r.id)
                    return (
                      <TableRow key={r.id} data-state={r.id === flow.run ? "selected" : undefined}>
                        <TableCell className="font-mono text-xs"><Link to={`/runs/${encodeURIComponent(r.id)}`} className="hover:underline">{r.id}</Link></TableCell>
                        <TableCell><SystemBadge system={r.system} /></TableCell>
                        <TableCell className="text-xs">{running ? "running" : r.complete ? "complete" : "incomplete"}{reports.has(r.id) ? ", scored" : ""}</TableCell>
                        <TableCell>{r.label ? <LabelBadge label={r.label} /> : "—"} <ErrorCallsBadge count={r.error_calls} /></TableCell>
                        <TableCell className="space-x-1 text-right whitespace-nowrap">
                          {r.kind === "engine" && (r.id === flow.run ? <Badge>chosen</Badge> : (
                            <Button size="sm" variant="outline" onClick={() => flow.set({ run: r.id }, { push: true })} aria-label={`Choose ${r.id}`}>Choose</Button>
                          ))}
                          {r.kind === "engine" && r.complete && !running && (
                            <Button size="xs" variant="outline" disabled={scoring || score.isPending} onClick={() => score.mutate({ run: r.id }, done)} aria-label={`Score ${r.id}`}>
                              <BarChart3Icon data-icon="inline-start" />
                              {reports.has(r.id) ? "Score again" : "Score"}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" disabled={scored.length < 2 || compare.isPending}
              onClick={() => compare.mutate({ reports: scored.map((r) => r.id), name: `compare-${corpus}` }, done)}>
              <GitCompareIcon data-icon="inline-start" />
              Compare the scored runs
            </Button>
            <span className="text-xs text-muted-foreground">
              {scored.length < 2 ? "Needs two scored engine runs (e.g. cascade all and gaps)." : `${scored.length} reports into scores/compare-${corpus}.`}
              {(scores.data?.compares ?? []).some((c) => c.id === `compare-${corpus}`) && <> <Link to={`/scores/compares/${encodeURIComponent(`compare-${corpus}`)}`} className="underline">Open the comparison</Link></>}
            </span>
          </div>
        </CardContent>
      </Card>
      {flow.run && (
        <Card>
          <CardHeader><CardTitle className="text-base">Chosen run <span className="font-mono">{flow.run}</span></CardTitle></CardHeader>
          <CardContent><SelectedRun id={flow.run} live={liveRun} /></CardContent>
        </Card>
      )}
    </div>
  )
}
