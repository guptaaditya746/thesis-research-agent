/**
 * Overview `/` (plan "Frontend pages" 1): one row per question with its concept, gold and runs
 * per condition and their mean scores, below four tiles that show how far the pipeline is
 * (concepts picked, keys reviewed, scored runs out of 12 x 2 x 3, the report).
 */
import { ArrowRightIcon, FlaskConicalIcon, GitCompareArrowsIcon } from "lucide-react"
import { Link } from "react-router"

import { useQuestions, useResults, useRuns } from "@/api/hooks"
import type { RunSummary } from "@/api/types"
import { ConceptBadge, GoldBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { pct } from "@/lib/format"

const PLANNED_RUNS = 12 * 2 * 3 // questions x conditions x repeats (plan: mean of 3 repeats)

interface Mean {
  value: number | null
  provisional: boolean
}

/** Mean support share over a question's scored runs of one condition (on its current concept). */
function meanSupport(runs: RunSummary[], qid: string, condition: string): Mean {
  const scored = runs.filter((r) => r.qid === qid && r.condition === condition && r.concept_current !== false && r.score?.support_share != null)
  const values = scored.map((r) => r.score!.support_share!)
  return {
    value: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    provisional: scored.some((r) => r.score?.provisional),
  }
}

function MeanCell({ mean }: { mean: Mean }) {
  return (
    <span className="inline-flex items-center gap-1">
      {mean.provisional && <FlaskConicalIcon className="size-3 text-status-warning" aria-label="provisional (draft key)" />}
      {pct(mean.value, 0)}
    </span>
  )
}

export default function OverviewPage() {
  const questions = useQuestions()
  const runs = useRuns()
  const results = useResults()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Twelve questions, two conditions: from the concept pick and the gold key to scored runs and the report."
      />
      <PipelineTiles />
      {runs.isError && (
        <ErrorState error={runs.error} title="Could not load the runs: run counts and support means are missing" onRetry={() => void runs.refetch()} />
      )}
      {results.isError && (
        <ErrorState error={results.error} title="Could not load the report" onRetry={() => void results.refetch()} />
      )}
      {questions.isError ? (
        <ErrorState error={questions.error} onRetry={() => void questions.refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Questions</CardTitle>
            <CardDescription>Runs on the current concept; support share: mean over the scored runs of each condition.</CardDescription>
          </CardHeader>
          <CardContent>
            {questions.isPending ? (
              <TableSkeleton rows={12} columns={6} />
            ) : (
              <Table>
                <caption className="sr-only">Questions and their pipeline state</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-14">Id</TableHead>
                    <TableHead>Question</TableHead>
                    <TableHead>Concept</TableHead>
                    <TableHead>Gold</TableHead>
                    <TableHead className="text-right">Runs on / off</TableHead>
                    <TableHead className="text-right">Support on / off</TableHead>
                    <TableHead className="w-10"><span className="sr-only">Compare</span></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {questions.data.map((q) => (
                    <TableRow key={q.id}>
                      <TableCell className="font-mono text-xs">{q.id}</TableCell>
                      <TableCell className="max-w-md min-w-56 whitespace-normal">
                        <Link to={`/earlier/questions/${q.id}`} className="font-medium hover:underline">
                          {q.question}
                        </Link>
                        {q.category && (
                          <div className="mt-1">
                            <Badge variant="secondary" className="font-normal">{q.category.replace("_", " ")}</Badge>
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-normal">
                        <ConceptBadge status={q.concept.status} pickedBy={q.concept.picked_by} />
                        {q.concept.title && <div className="mt-1 max-w-56 text-xs text-muted-foreground">{q.concept.title}</div>}
                      </TableCell>
                      <TableCell>
                        <GoldBadge status={q.gold.status} />
                        {q.gold.facts != null && (
                          <div className="mt-1 text-xs text-muted-foreground tabular-nums">
                            {q.gold.rows} rows · {q.gold.facts} facts
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        <Link to={`/earlier/runs?qid=${q.id}`} className="hover:underline" aria-label={`Runs of ${q.id}`}>
                          {q.runs.claim_on ?? 0} / {q.runs.claim_off ?? 0}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {runs.isPending ? (
                          <Skeleton className="ml-auto h-4 w-20" />
                        ) : runs.isError ? (
                          <span className="text-xs text-destructive">not loaded</span>
                        ) : (
                          <>
                            <MeanCell mean={meanSupport(runs.data ?? [], q.id, "claim_on")} /> / <MeanCell mean={meanSupport(runs.data ?? [], q.id, "claim_off")} />
                          </>
                        )}
                      </TableCell>
                      <TableCell>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button asChild variant="ghost" size="icon-sm" aria-label={`Compare conditions for ${q.id}`}>
                              <Link to={`/earlier/compare/${q.id}`}>
                                <GitCompareArrowsIcon />
                              </Link>
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Compare claim on and claim off</TooltipContent>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
      {results.data && (
        <Button asChild variant="outline">
          <Link to="/earlier/results">
            The report is ready: primary test and charts
            <ArrowRightIcon data-icon="inline-end" />
          </Link>
        </Button>
      )}
    </div>
  )
}

function PipelineTiles() {
  const questions = useQuestions()
  const runs = useRuns()
  const results = useResults()
  const total = questions.data?.length || 12
  const picked = questions.data?.filter((q) => q.concept.status === "picked").length ?? 0
  const reviewed = questions.data?.filter((q) => q.gold.status === "reviewed").length ?? 0
  const drafts = questions.data?.filter((q) => q.gold.status === "draft").length ?? 0
  const scored = runs.data?.filter((r) => r.score !== null && !r.live && !r.score.provisional).length ?? 0
  const provisional = runs.data?.filter((r) => r.score?.provisional).length ?? 0
  const live = runs.data?.filter((r) => r.live).length ?? 0
  const report = results.data

  const tiles = [
    { label: "Concepts picked", value: `${picked} of ${total}`, share: picked / total, note: "a brief per question", pending: questions.isPending, error: questions.isError },
    { label: "Gold keys reviewed", value: `${reviewed} of ${total}`, share: reviewed / total, note: `${drafts} draft`, pending: questions.isPending, error: questions.isError },
    {
      label: "Runs scored", value: `${scored} of ${PLANNED_RUNS}`, share: scored / PLANNED_RUNS,
      note: [live ? `${live} running now` : "12 questions × 2 conditions × 3", provisional ? `${provisional} against draft keys` : ""].filter(Boolean).join(" · "),
      pending: runs.isPending,
      error: runs.isError,
    },
    {
      label: "Report", value: report ? (report.provisional ? "provisional" : "ready") : "not yet", share: report ? 1 : 0,
      note: report ? `${report.runs?.scored ?? "?"} scored runs${report.complete === false ? " · verdicts pending" : ""}` : "`score report` after all runs",
      pending: results.isPending,
      // a 404 is "no report yet" (null); anything else is an error, not "not yet"
      error: results.isError,
    },
  ]
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((t) => (
        <Card key={t.label} className="gap-2">
          <CardHeader>
            <CardDescription>{t.label}</CardDescription>
            <CardTitle className="text-2xl font-semibold">
              {t.error ? <span className="text-destructive">not loaded</span> : t.pending ? <Skeleton className="h-7 w-24" /> : t.value}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {t.error ? (
              <p className="text-xs text-destructive">The request failed; see the error above.</p>
            ) : (
              <>
                <Progress value={Math.round(t.share * 100)} aria-label={`${t.label}: ${Math.round(t.share * 100)}%`} />
                <p className="text-xs text-muted-foreground">{t.note}</p>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
