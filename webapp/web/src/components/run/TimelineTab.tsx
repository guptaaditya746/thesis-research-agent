/**
 * Timeline tab: the run's steps in order, live while the run is going (the run stream folded
 * into the summarised steps, src/api/stream.ts), with the budget line, phase changes (research
 * -> conclude, attach), coverage notices and each step's claims. Successor of the static
 * timeline.html of row 1.14.
 */
import { ArrowRightIcon, CheckIcon, GitBranchIcon, RotateCwIcon, TriangleAlertIcon, XIcon } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { useSteps } from "@/api/hooks"
import { useRunStream, type StreamStatus } from "@/api/stream"
import type { RunConfig } from "@/api/types"
import { LiveDot } from "@/components/badges"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Switch } from "@/components/ui/switch"
import { duration, int, tokens as fmtTokens } from "@/lib/format"
import { summarize, type TimelineStep } from "@/lib/timeline"
import { cn } from "@/lib/utils"

import { StepView } from "./ClaimWalkSheet"

/** What each coverage reason (agent/loop.py, agent/batch.py) means, for the notice. */
const COVERAGE: Record<string, string> = {
  unparsed: "The reply had no bash block and no answer; nothing ran and the agent was nudged.",
  invalid_final_answer: "The final answer did not validate against the concept's answer schema.",
  command_not_run: "A command came during the conclude phase; it was not run.",
  no_final_answer: "The run ended without a valid answer; answer.json has no rows.",
  run_error: "The run stopped on an error.",
  job_time_limit: "The batch job's time limit cut the run; it is rerun fresh.",
}

const STREAM_LABEL: Record<StreamStatus, string> = {
  idle: "not live",
  connecting: "connecting",
  open: "streaming",
  done: "finished",
  error: "stream lost, reconnecting",
}

export function TimelineTab({ runId, live, budget }: { runId: string; live: boolean; budget: RunConfig["budget"] | undefined }) {
  const steps = useSteps(runId)
  const { timeline, status, reconnect } = useRunStream(runId, { live, seed: steps.data })
  const summary = summarize(timeline)
  const [follow, setFollow] = useState(true)
  const end = useRef<HTMLDivElement>(null)
  const count = summary.steps.length

  useEffect(() => {
    if (live && follow) end.current?.scrollIntoView({ block: "end", behavior: "smooth" })
  }, [count, live, follow])

  if (steps.isPending) return <TableSkeleton rows={6} columns={3} />
  if (steps.isError && summary.steps.length === 0) {
    return <ErrorState error={steps.error} onRetry={() => void steps.refetch()} />
  }

  const phaseAt = new Map(summary.phaseChanges.map((c) => [c.at, c]))
  return (
    <div className="space-y-4">
      <Card className="py-4">
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <BudgetMeter label="Research steps" used={summary.researchSteps} limit={budget?.steps} format={int} />
          <BudgetMeter label="Tokens" used={summary.tokens} limit={budget?.tokens} format={fmtTokens} />
          <div className="space-y-1 text-sm">
            <p className="text-muted-foreground">Claims</p>
            <p className="tabular-nums">
              <CheckIcon className="inline size-3.5 text-status-good" aria-label="accepted" /> {summary.claimsAccepted}
              <XIcon className="ml-3 inline size-3.5 text-status-critical" aria-label="rejected" /> {summary.claimsRejected}
            </p>
          </div>
          <div className="space-y-1 text-sm">
            <p className="text-muted-foreground">Stream</p>
            <div className="flex flex-wrap items-center gap-2">
              {status === "open" && <LiveDot />}
              <span>{STREAM_LABEL[live || status === "done" ? status : "idle"]}</span>
              {status === "error" && (
                <Button size="xs" variant="outline" onClick={reconnect}>
                  <RotateCwIcon data-icon="inline-start" /> Reconnect
                </Button>
              )}
            </div>
            {live && (
              <div className="flex items-center gap-2">
                <Switch id="timeline-follow" checked={follow} onCheckedChange={setFollow} />
                <Label htmlFor="timeline-follow" className="text-xs">Follow new steps</Label>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
      {summary.steps.length === 0 ? (
        <EmptyState title="No steps yet" description={live ? "The first model call is on its way." : "events.jsonl has no records."} />
      ) : (
        <ol className="space-y-3" aria-label="Steps">
          {summary.steps.map((s) => {
            const change = phaseAt.get(s.key)
            return (
              <li key={s.key} className="space-y-3">
                {change && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground" role="separator" aria-label={`Phase ${change.from} to ${change.to}`}>
                    <span className="h-px flex-1 bg-border" />
                    phase {change.from} <ArrowRightIcon className="size-3" aria-hidden="true" /> <span className="font-medium text-foreground">{change.to}</span>
                    <span className="h-px flex-1 bg-border" />
                  </div>
                )}
                <StepCard runId={runId} step={s} />
              </li>
            )
          })}
        </ol>
      )}
      <div ref={end} />
    </div>
  )
}

function BudgetMeter({ label, used, limit, format }: { label: string; used: number; limit: number | undefined; format: (n: number) => string }) {
  const share = limit ? Math.min(1, used / limit) : 0
  return (
    <div className="space-y-1 text-sm">
      <p className="text-muted-foreground">{label}</p>
      <p className="tabular-nums">
        {format(used)}
        {limit ? <span className="text-muted-foreground"> of {format(limit)}</span> : null}
      </p>
      {limit ? (
        <Progress
          value={Math.round(share * 100)}
          aria-label={`${label}: ${Math.round(share * 100)}% of the budget`}
          className={cn(share >= 0.9 && "[&>[data-slot=progress-indicator]]:bg-status-critical", share >= 0.75 && share < 0.9 && "[&>[data-slot=progress-indicator]]:bg-status-warning")}
        />
      ) : null}
    </div>
  )
}

function StepCard({ runId, step }: { runId: string; step: TimelineStep }) {
  return (
    <Card className={cn("gap-3 py-3", step.agent_id !== "main" && "ml-6 border-dashed")}>
      <CardContent className="space-y-2 px-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium tabular-nums">Step {step.step}</span>
          {step.agent_id !== "main" && (
            <Badge variant="outline" className="gap-1 font-mono font-normal"><GitBranchIcon className="size-3" aria-hidden="true" />{step.agent_id}</Badge>
          )}
          {step.phase && <Badge variant="secondary" className="font-normal">{step.phase}</Badge>}
          {step.origin === "attach" && <Badge variant="outline" className="font-normal">attach</Badge>}
          {step.final_answer && <Badge className="font-normal">final answer</Badge>}
          {step.model_call?.reply === "answer" && !step.final_answer && <Badge variant="outline" className="font-normal">answer reply</Badge>}
          {step.spawned.length > 0 && <span className="text-xs text-muted-foreground">spawned {step.spawned.join(", ")}</span>}
          {step.model_call?.seconds != null && <span className="ml-auto text-xs text-muted-foreground tabular-nums">{duration(step.model_call.seconds)}</span>}
        </div>
        <StepView
          runId={runId}
          step={{
            step: step.step, phase: step.phase ?? "", model_call: step.model_call, command: step.command, exit_code: step.exit_code,
            timed_out: step.timed_out, output_head: step.output_head, output_bytes: step.output_bytes, claims: step.claims,
            coverage: step.coverage, agent_id: step.agent_id, origin: step.origin,
          }}
        />
        {step.claims.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Claims of this step">
            {step.claims.map((c, i) => (
              <li key={c.claim_id ?? `rejected-${i}`}>
                <Badge variant="outline" className="max-w-full gap-1 font-normal whitespace-normal">
                  {c.status === "accepted" ? (
                    <CheckIcon className="text-status-good" aria-label="accepted" />
                  ) : (
                    <XIcon className="text-status-critical" aria-label="rejected" />
                  )}
                  <span className="font-mono">{c.claim_id ?? c.reason}</span>
                  {c.s && <span className="text-muted-foreground">({c.s}, {c.p}, {String(c.o)})</span>}
                </Badge>
              </li>
            ))}
          </ul>
        )}
        {step.coverage.map((reason) => (
          <Alert key={reason} className="border-status-warning/50 py-2">
            <TriangleAlertIcon className="text-status-warning" />
            <AlertTitle className="font-mono text-xs">coverage: {reason}</AlertTitle>
            <AlertDescription className="text-xs">{COVERAGE[reason] ?? "Recorded by the harness."}</AlertDescription>
          </Alert>
        ))}
      </CardContent>
    </Card>
  )
}
