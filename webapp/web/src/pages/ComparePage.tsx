/**
 * Compare `/compare/:qid` (plan "Frontend pages" 5): a claim_on run and a claim_off run of one
 * question side by side: their answers with fact badges (each opens that run's claim walk),
 * the support of their facts and their cost, and the differences on top. The runs are
 * picked per condition (?on=&off=); by default the latest finished run of each.
 */
import { GitCompareArrowsIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router"

import { useQuestion, useRun, useRuns, useScore } from "@/api/hooks"
import type { Condition, RunSummary } from "@/api/types"
import { ConditionBadge, ExitBadge, VerifyBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ClaimWalkSheet } from "@/components/run/ClaimWalkSheet"
import { FactBadge } from "@/components/run/FactBadge"
import { SupportBar } from "@/components/run/ScoreTab"
import { useFactStatuses } from "@/components/run/use-fact-statuses"
import { WalkContext, type WalkTarget } from "@/components/run/walk-context"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { isGraphRow } from "@/lib/facts"
import { cell, CONDITION_LABEL, duration, pct, pp, tokens } from "@/lib/format"

const PARAM: Record<Condition, string> = { claim_on: "on", claim_off: "off" }

/** The latest run of a condition that finished, else the latest at all. */
function defaultRun(runs: RunSummary[], condition: Condition): string | undefined {
  const of = runs.filter((r) => r.condition === condition).sort((a, b) => b.created_at.localeCompare(a.created_at))
  return (of.find((r) => !r.live && r.exit_status === "submitted") ?? of[0])?.run_id
}

export default function ComparePage() {
  const { qid = "" } = useParams()
  const question = useQuestion(qid)
  const runs = useRuns({ qid })
  const [params, setParams] = useSearchParams()

  const chosen = (c: Condition) => params.get(PARAM[c]) ?? (runs.data ? defaultRun(runs.data, c) : undefined)
  const on = chosen("claim_on")
  const off = chosen("claim_off")
  const choose = (c: Condition, runId: string) => {
    const next = new URLSearchParams(params)
    next.set(PARAM[c], runId)
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={<span className="flex items-center gap-2"><GitCompareArrowsIcon className="size-5" aria-hidden="true" /> Compare {qid}</span>}
        description={question.data?.question ?? <Skeleton className="h-4 w-96 max-w-full" />}
      />
      {runs.isError ? (
        <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
      ) : runs.isPending ? (
        <TableSkeleton rows={6} columns={4} />
      ) : runs.data.length === 0 ? (
        <EmptyState title={`No runs of ${qid} yet`} description="Start a claim_on and a claim_off run with the same seed to compare them.">
          <Link to={`/runs?qid=${qid}`} className="text-sm underline">Runs of {qid}</Link>
        </EmptyState>
      ) : (
        <>
          <Differences on={on} off={off} />
          <div className="grid gap-4 lg:grid-cols-2">
            {(["claim_on", "claim_off"] as const).map((c) => (
              <div key={c} className="space-y-3">
                <div className="space-y-1">
                  <Label htmlFor={`compare-${c}`} className="text-xs text-muted-foreground">{CONDITION_LABEL[c]} run</Label>
                  <Select value={chosen(c) ?? ""} onValueChange={(v) => choose(c, v)}>
                    <SelectTrigger id={`compare-${c}`} className="w-full"><SelectValue placeholder={`No ${CONDITION_LABEL[c]} run`} /></SelectTrigger>
                    <SelectContent>
                      {runs.data.filter((r) => r.condition === c).map((r) => (
                        <SelectItem key={r.run_id} value={r.run_id}>
                          <span className="font-mono">{r.run_id}</span> · seed {r.seed} · {r.live ? "running" : (r.exit_status ?? "?")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {chosen(c) ? (
                  <RunColumn key={chosen(c)} runId={chosen(c)!} />
                ) : (
                  <EmptyState title={`No ${CONDITION_LABEL[c]} run`} description={`Start a ${CONDITION_LABEL[c]} run of ${qid} to fill this side.`} />
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Differences({ on, off }: { on?: string; off?: string }) {
  const a = useScore(on ?? "", !!on)
  const b = useScore(off ?? "", !!off)
  if (!a.data || !b.data) return null
  const diff = (x: number | null, y: number | null) => (x !== null && y !== null ? x - y : null)
  const items = [
    { label: "Support share", value: pp(diff(a.data.support.support_share, b.data.support.support_share)) },
    { label: "Fact F1 (soft)", value: pp(diff(a.data.facts.soft.f1, b.data.facts.soft.f1)) },
    { label: "Unsourced facts", value: `${a.data.support.unsourced} vs ${b.data.support.unsourced}` },
    { label: "Tokens", value: `${tokens(a.data.cost.tokens)} vs ${tokens(b.data.cost.tokens)} (${tokens(b.data.cost.tokens_without_attach)} without attach)` },
    { label: "Time", value: `${duration(a.data.cost.seconds)} vs ${duration(b.data.cost.seconds)}` },
  ]
  return (
    <Card className="gap-2 py-4">
      <CardHeader>
        <CardTitle className="text-sm">claim on minus claim off</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5">
          {items.map((i) => (
            <div key={i.label}>
              <dt className="text-xs text-muted-foreground">{i.label}</dt>
              <dd className="font-medium tabular-nums">{i.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function RunColumn({ runId }: { runId: string }) {
  const run = useRun(runId)
  const score = useScore(runId)
  const statuses = useFactStatuses(runId, run.data?.answer)
  const [walk, setWalk] = useState<WalkTarget | null>(null)
  const api = useMemo(() => ({ runId, open: setWalk }), [runId])

  if (run.isPending) return <Skeleton className="h-96 w-full" />
  if (run.isError) return <ErrorState error={run.error} onRetry={() => void run.refetch()} />
  const { summary: s, answer } = run.data

  return (
    <WalkContext.Provider value={api}>
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            <Link to={`/runs/${runId}`} className="font-mono hover:underline">{runId}</Link>
            <ConditionBadge condition={s.condition} />
          </CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-2">
            <ExitBadge status={s.exit_status} live={s.live} />
            <VerifyBadge verify={s.verify} />
            <span className="tabular-nums">{tokens(s.tokens)} tokens · {duration(s.seconds)} · {s.claims_accepted} claims</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {score.data ? (
            <SupportBar support={score.data.support} />
          ) : (
            <p className="text-sm text-muted-foreground">Not scored yet: support from the judge verdicts per fact below.</p>
          )}
          {score.data && (
            <p className="text-sm">
              Support share <span className="font-medium tabular-nums">{pct(score.data.support.support_share)}</span> · fact F1{" "}
              <span className="font-medium tabular-nums">{score.data.facts.soft.f1?.toFixed(2) ?? "—"}</span>
            </p>
          )}
          {!answer || answer.rows.length === 0 ? (
            <EmptyState title="No answer" description={answer?.notes ?? (s.live ? "The run is still going." : "answer.json has no rows.")} />
          ) : (
            <ul className="divide-y rounded-md border" aria-label={`Answer of ${runId}`}>
              {answer.rows.map((row) => (
                <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                  <span className="min-w-0">
                    <span className="mr-2 font-mono text-xs text-muted-foreground">{row.id}</span>
                    {isGraphRow(row) ? (
                      <>
                        {row.source} <span className="font-mono text-xs text-muted-foreground">{row.predicate}</span> {row.target}
                      </>
                    ) : (
                      Object.values(row.cells).slice(0, 3).map(cell).join(" · ")
                    )}
                  </span>
                  <span className="flex flex-wrap gap-1">
                    {row.facts.map((f) => {
                      const st = statuses.get(f.id) ?? { status: "unjudged" as const, loading: false }
                      return <FactBadge key={f.id} fact={f} status={st.status} loading={st.loading} onOpen={() => setWalk({ kind: "fact", factId: f.id })} />
                    })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <ClaimWalkSheet runId={runId} target={walk} onClose={() => setWalk(null)} />
    </WalkContext.Provider>
  )
}
