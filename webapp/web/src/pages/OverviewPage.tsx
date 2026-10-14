/**
 * Overview `/` (plan "Frontend pages" 1): one row per question with its concept, gold and runs
 * per condition and their mean scores, above four tiles that show how far the pipeline is
 * (concepts picked, keys reviewed, scored runs out of 12 x 2 x 3, the report).
 */
import { ArrowRightIcon, GitCompareArrowsIcon } from "lucide-react"
import { Link } from "react-router"

import { useGold, useQuestions, useResults, useRuns } from "@/api/hooks"
import type { Condition, RunSummary } from "@/api/types"
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

function meanSupport(runs: RunSummary[], qid: string, condition: Condition): number | null {
  const values = runs
    .filter((r) => r.qid === qid && r.condition === condition && r.score?.support_share != null)
    .map((r) => r.score!.support_share!)
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

export default function OverviewPage() {
  const questions = useQuestions()
  const runs = useRuns()
  const gold = useGold()
  const results = useResults()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Twelve questions, two conditions: from the concept pick and the gold key to scored runs and the report."
      />
      <PipelineTiles />
      {questions.isError ? (
        <ErrorState error={questions.error} onRetry={() => void questions.refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Questions</CardTitle>
            <CardDescription>Support share: mean over the scored runs of the condition.</CardDescription>
          </CardHeader>
          <CardContent>
            {questions.isPending ? (
              <TableSkeleton rows={12} columns={6} />
            ) : (
              <Table>
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
                  {questions.data.map((q) => {
                    const on = meanSupport(runs.data ?? [], q.id, "claim_on")
                    const off = meanSupport(runs.data ?? [], q.id, "claim_off")
                    const g = gold.data?.find((x) => x.qid === q.id)
                    return (
                      <TableRow key={q.id}>
                        <TableCell className="font-mono text-xs">{q.id}</TableCell>
                        <TableCell className="max-w-md whitespace-normal">
                          <Link to={`/questions/${q.id}`} className="font-medium hover:underline">
                            {q.question}
                          </Link>
                          <div className="mt-1">
                            <Badge variant="secondary" className="font-normal">{q.category.replace("_", " ")}</Badge>
                          </div>
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          <ConceptBadge status={q.concept.status} pickedBy={q.concept.picked_by} />
                          {q.concept.title && <div className="mt-1 max-w-56 text-xs text-muted-foreground">{q.concept.title}</div>}
                        </TableCell>
                        <TableCell>
                          <GoldBadge status={g?.status ?? q.gold.status} />
                          {q.gold.facts != null && (
                            <div className="mt-1 text-xs text-muted-foreground tabular-nums">
                              {q.gold.rows} rows · {q.gold.facts} facts
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          <Link to={`/runs?qid=${q.id}`} className="hover:underline" aria-label={`Runs of ${q.id}`}>
                            {q.runs.claim_on} / {q.runs.claim_off}
                          </Link>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {runs.isPending ? <Skeleton className="ml-auto h-4 w-20" /> : `${pct(on, 0)} / ${pct(off, 0)}`}
                        </TableCell>
                        <TableCell>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button asChild variant="ghost" size="icon-sm" aria-label={`Compare conditions for ${q.id}`}>
                                <Link to={`/compare/${q.id}`}>
                                  <GitCompareArrowsIcon />
                                </Link>
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Compare claim on and claim off</TooltipContent>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
      {results.data && (
        <Button asChild variant="outline">
          <Link to="/results">
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
  const gold = useGold()
  const results = useResults()
  const total = questions.data?.length ?? 12
  const picked = questions.data?.filter((q) => q.concept.status === "picked").length ?? 0
  const reviewed = gold.data?.filter((g) => g.status === "reviewed").length ?? 0
  const drafts = gold.data?.filter((g) => g.status === "draft").length ?? 0
  const scored = runs.data?.filter((r) => r.score !== null && !r.live).length ?? 0
  const live = runs.data?.filter((r) => r.live).length ?? 0

  const tiles = [
    { label: "Concepts picked", value: `${picked} of ${total}`, share: picked / total, note: "a brief per question", pending: questions.isPending },
    { label: "Gold keys reviewed", value: `${reviewed} of ${total}`, share: reviewed / total, note: `${drafts} draft`, pending: gold.isPending },
    { label: "Runs scored", value: `${scored} of ${PLANNED_RUNS}`, share: scored / PLANNED_RUNS, note: live ? `${live} running now` : "12 questions × 2 conditions × 3", pending: runs.isPending },
    { label: "Report", value: results.data ? "ready" : "not yet", share: results.data ? 1 : 0, note: results.data ? `key ${results.data.key_version ?? "?"}` : "score report after all runs", pending: results.isPending },
  ]
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((t) => (
        <Card key={t.label} className="gap-2">
          <CardHeader>
            <CardDescription>{t.label}</CardDescription>
            <CardTitle className="text-2xl font-semibold">{t.pending ? <Skeleton className="h-7 w-24" /> : t.value}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Progress value={Math.round(t.share * 100)} aria-label={`${t.label}: ${Math.round(t.share * 100)}%`} />
            <p className="text-xs text-muted-foreground">{t.note}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
