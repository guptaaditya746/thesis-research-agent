/**
 * Compare `/earlier/compare/:qid` (plan "Frontend pages" 5): a claim_on run and a claim_off run of one
 * question side by side: their answers with fact badges (each opens that run's claim walk), the
 * support of their facts and their cost, and the differences on top. The runs are picked per
 * condition (?on=&off=); by default the latest finished run of each, preferring the same seed.
 */
import { GitCompareArrowsIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router"

import { useQuestion, useRun, useRuns, useScore } from "@/api/hooks"
import type { Condition, RunSummary } from "@/api/types"
import { ConditionBadge, ExitBadge, ProvisionalBadge, SandboxBadge, VerifyBadge } from "@/components/badges"
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
import { isGraphRow, statusOf } from "@/lib/facts"
import { cell, CONDITION_LABEL, duration, num, pct, pp, signed, tokens } from "@/lib/format"
import { splitRunId } from "@/lib/run"

const PARAM: Record<Condition, string> = { claim_on: "on", claim_off: "off" }

const byNewest = (a: RunSummary, b: RunSummary) => (b.created_at ?? "").localeCompare(a.created_at ?? "")

/** The latest finished run of a condition (same seed as `seed` if there is one), else the latest at all. */
function defaultRun(runs: RunSummary[], condition: Condition, seed?: number | null): string | undefined {
  const of = runs.filter((r) => r.condition === condition).sort(byNewest)
  const finished = of.filter((r) => !r.live && r.exit_status === "submitted")
  return (finished.find((r) => seed != null && r.seed === seed) ?? finished[0] ?? of[0])?.run_id
}

export default function ComparePage() {
  const { qid = "" } = useParams()
  const question = useQuestion(qid)
  const runs = useRuns({ qid })
  const [params, setParams] = useSearchParams()

  const all = runs.data ?? []
  const on = params.get(PARAM.claim_on) ?? defaultRun(all, "claim_on")
  const off = params.get(PARAM.claim_off) ?? defaultRun(all, "claim_off", all.find((r) => r.run_id === on)?.seed)
  const chosen: Record<Condition, string | undefined> = { claim_on: on, claim_off: off }
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
      ) : all.length === 0 ? (
        <EmptyState title={`No runs of ${qid} yet`} description="Start a claim_on and a claim_off run with the same seed to compare them (New run, both conditions).">
          <Link to={`/earlier/runs?qid=${qid}`} className="text-sm underline">Runs of {qid}</Link>
        </EmptyState>
      ) : (
        <>
          <Differences on={on} off={off} />
          <div className="grid gap-4 lg:grid-cols-2">
            {(["claim_on", "claim_off"] as const).map((c) => (
              <div key={c} className="min-w-0 space-y-3">
                <div className="space-y-1">
                  <Label htmlFor={`compare-${c}`} className="text-xs text-muted-foreground">{CONDITION_LABEL[c]} run</Label>
                  <Select value={chosen[c] ?? ""} onValueChange={(v) => choose(c, v)}>
                    <SelectTrigger id={`compare-${c}`} className="w-full"><SelectValue placeholder={`No ${CONDITION_LABEL[c]} run`} /></SelectTrigger>
                    <SelectContent>
                      {all.filter((r) => r.condition === c).map((r) => (
                        <SelectItem key={r.run_id} value={r.run_id}>
                          <span className="font-mono">{splitRunId(r.run_id).name}</span> · seed {r.seed ?? "—"} · {r.live ? "running" : r.exit_status}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {chosen[c] ? (
                  <RunColumn key={chosen[c]} runId={chosen[c]!} />
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
  if (!on || !off) return null
  if (a.isError || b.isError) {
    return (
      <ErrorState
        error={a.error ?? b.error}
        title="Could not load the scores to compare"
        onRetry={() => {
          if (a.isError) void a.refetch()
          if (b.isError) void b.refetch()
        }}
      />
    )
  }
  if (a.isPending || b.isPending) return <Skeleton className="h-24 w-full" />
  if (!a.data || !b.data) {
    return <p className="text-sm text-muted-foreground">The differences appear when both runs are scored.</p>
  }
  const diff = (x: number | null | undefined, y: number | null | undefined) => (x != null && y != null ? x - y : null)
  const [sa, sb] = [a.data, b.data]
  const items = [
    { label: "Support share", value: pp(diff(sa.support?.support_share, sb.support?.support_share)), detail: `${pct(sa.support?.support_share)} vs ${pct(sb.support?.support_share)}` },
    { label: "Fact F1 (soft)", value: signed(diff(sa.facts?.soft?.f1, sb.facts?.soft?.f1), (v) => v.toFixed(2)), detail: `${num(sa.facts?.soft?.f1)} vs ${num(sb.facts?.soft?.f1)}` },
    { label: "Unsourced facts", value: `${sa.support?.unsourced ?? "—"} vs ${sb.support?.unsourced ?? "—"}`, detail: `${pct(sa.support?.unsourced_share, 0)} vs ${pct(sb.support?.unsourced_share, 0)}` },
    { label: "Tokens", value: `${tokens(sa.cost?.tokens)} vs ${tokens(sb.cost?.tokens)}`, detail: `${tokens(sb.cost?.tokens_without_attach)} without attach` },
    { label: "Time", value: `${duration(sa.cost?.seconds)} vs ${duration(sb.cost?.seconds)}`, detail: `${duration(sb.cost?.seconds_without_attach)} without attach` },
  ]
  return (
    <Card className="gap-2 py-4">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
          claim on minus claim off
          {(sa.provisional || sb.provisional) && <ProvisionalBadge />}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5">
          {items.map((i) => (
            <div key={i.label}>
              <dt className="text-xs text-muted-foreground">{i.label}</dt>
              <dd className="font-medium tabular-nums">{i.value}</dd>
              <dd className="text-xs text-muted-foreground tabular-nums">{i.detail}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function RunColumn({ runId }: { runId: string }) {
  const run = useRun(runId)
  const { statuses, score, error: scoreError, retry } = useFactStatuses(runId, run.data?.answer)
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
            <Link to={`/earlier/runs/${encodeURIComponent(runId)}`} className="font-mono break-all hover:underline">{splitRunId(runId).name}</Link>
            <ConditionBadge condition={s.condition} />
          </CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-2">
            <ExitBadge status={s.exit_status} live={s.live} />
            <VerifyBadge verify={s.verify} />
            <SandboxBadge mode={s.sandbox} />
            <span className="tabular-nums">seed {s.seed ?? "—"} · {tokens(s.tokens)} tokens · {duration(s.seconds)} · {s.claims_accepted} claims</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {score?.support ? (
            <>
              <SupportBar support={score.support} />
              <p className="text-sm">
                Support share <span className="font-medium tabular-nums">{pct(score.support.support_share)}</span> · fact F1{" "}
                <span className="font-medium tabular-nums">{num(score.facts?.soft?.f1)}</span>
              </p>
            </>
          ) : scoreError ? (
            <ErrorState error={scoreError} title="Could not load score.json: the facts below show only whether they cite a claim" onRetry={retry} />
          ) : (
            <p className="text-sm text-muted-foreground">Not scored yet: the facts below show whether they cite a claim.</p>
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
                      Object.values(row.cells ?? {}).slice(0, 3).map(cell).join(" · ")
                    )}
                  </span>
                  <span className="flex flex-wrap gap-1">
                    {row.facts.map((f) => (
                      <FactBadge key={f.id} fact={f} status={statusOf(statuses, row.id, f)} onOpen={() => setWalk({ kind: "fact", factId: f.id })} />
                    ))}
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
