/**
 * Home `/`: select a question (evidence/questions.yaml; never typed) to open its guided flow, the supervisor's
 * order (STATE.md §1, §4): question → protocol → corpus → run → evidence graph → answer → scores, the
 * baselines beside the engine. Below: what is on disk, the active jobs, and the directories the app reads and
 * its jobs write.
 */
import { ArrowRightIcon, ListOrderedIcon } from "lucide-react"
import { Link } from "react-router"

import { isActiveJob, useCorpora, useEvConfig, useEvRuns, useJobs, useQuestions, useScores } from "@/api/ev"
import { JobPanel } from "@/components/jobs/JobPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, CardsSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export default function HomePage() {
  const config = useEvConfig()
  const questions = useQuestions()
  const corpora = useCorpora()
  const runs = useEvRuns()
  const scores = useScores()
  const jobs = useJobs()
  const active = (jobs.data ?? []).filter(isActiveJob)
  return (
    <div className="space-y-6">
      <PageHeader title="Evidence-level synthesis" description="Select a question. Its flow goes question → protocol → corpus → run → evidence graph → answer → scores, the baselines beside the engine, and starts each missing step as a job." />
      <section aria-label="Questions" className="space-y-3">
        {questions.isPending ? <CardsSkeleton count={1} /> : questions.isError ? <ErrorState error={questions.error} title="The questions file does not validate" /> : questions.data.length === 0 ? (
          <EmptyState icon={<ListOrderedIcon />} title="No questions" description={`Add one to ${config.data?.questions.path ?? "evidence/questions.yaml"}.`} />
        ) : questions.data.map((q) => (
          <Card key={q.id} className="relative">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-lg text-balance">
                <Link to={`/flow/${encodeURIComponent(q.id)}`} className="after:absolute after:inset-0 hover:underline">{q.question}</Link>
                <ArrowRightIcon className="size-4 text-muted-foreground" aria-hidden="true" />
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{q.id}</span>
                {q.protocol ? <Badge variant="secondary">hand-written protocol {q.protocol}</Badge> : <Badge variant="outline">no protocol yet: propose one</Badge>}
                {q.agentic_protocol && <Badge variant="outline">agentic variant</Badge>}
                {q.proposals.length > 0 && <Badge variant="outline">{q.proposals.length} proposal(s)</Badge>}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </section>
      {/* one line once every count is in, not a row of "…" filling in one by one */}
      {corpora.isPending || runs.isPending || scores.isPending ? <Skeleton className="h-5 w-full max-w-2xl" aria-label="Counting what is on disk" /> : (
        <p className="text-sm text-muted-foreground">
          On disk: {corpora.data?.length ?? "?"} corpora, {runs.data?.filter((r) => r.kind === "engine").length ?? "?"} engine runs,{" "}
          {runs.data?.filter((r) => r.kind === "baseline").length ?? "?"} baseline answers, {scores.data?.reports.length ?? "?"} score reports
          (made here, on the command line or on Slurm: the same layout).
        </p>
      )}
      {active.length > 0 && (
        <section aria-label="Active jobs" className="space-y-2">
          <h2 className="text-base font-semibold">Running now</h2>
          {active.map((j) => <JobPanel key={j.id} job={j} compact />)}
        </section>
      )}
      {config.data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Directories and model</CardTitle>
            <CardDescription>
              {config.data.ev ? <>From <span className="font-mono">$EV</span> = <span className="font-mono">{config.data.ev}</span>.</> : "Set $EV when starting `webapp serve`: without it nothing can be started."}
              {" "}Model jobs use <span className="font-mono">{config.data.default_model}</span> at {config.data.llm_base_url}
              {config.data.llm_key_set ? "" : " (no $LITELLM_MASTER_KEY in the server's environment: model jobs will fail)"}; {config.data.model_jobs} at a time.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-1 text-sm sm:grid-cols-2">
              {(["corpora", "runs", "scores", "proposals", "cache", "agent_work", "protocols", "questions", "jobs"] as const).map((k) => {
                const root = config.data[k]
                return (
                  <li key={k} className="flex min-w-0 items-center gap-2">
                    <span className={cn("size-2 shrink-0 rounded-full", root.exists ? "bg-status-good" : "bg-muted-foreground/50")} aria-hidden="true" />
                    <span className="w-24 shrink-0 text-muted-foreground">{k.replace("_", " ")}</span>
                    <span className="truncate font-mono text-xs" title={root.path ?? undefined}>{root.path ?? "not configured"}</span>
                    {!root.exists && root.path && <span className="text-xs text-muted-foreground">(missing)</span>}
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
