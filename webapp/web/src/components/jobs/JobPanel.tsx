/**
 * One job as the flow and the Jobs page show it: what it writes, its state and lane, its steps with their
 * command lines, the tail of its log (polled while it runs) and Cancel. A queued model job says it waits for the
 * model; the log is the commands' own output.
 */
import { ExternalLinkIcon, SquareIcon } from "lucide-react"
import { Link, useNavigate } from "react-router"

import { isActiveJob, useCancelJob, useJobLog, type Job } from "@/api/ev"
import { JobBadge } from "@/components/badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { dateTime, duration, elapsed } from "@/lib/format"
import { jobTarget, jobTitle } from "@/lib/jobs"
import { announceError } from "@/lib/toasts"

export function JobLog({ job, lines = 40 }: { job: Job; lines?: number }) {
  const log = useJobLog(job.id, isActiveJob(job), lines)
  return (
    <pre aria-label={`Log of job ${job.id}`} className="max-h-72 overflow-auto rounded-md bg-muted p-2 font-mono text-xs leading-relaxed whitespace-pre-wrap">
      {log.data ?? (log.isPending ? "…" : "")}
      {log.data === "" && (job.state === "queued" ? "waiting for its turn" : "no output yet")}
    </pre>
  )
}

export function JobPanel({ job, compact = false }: { job: Job; compact?: boolean }) {
  const cancel = useCancelJob()
  const navigate = useNavigate()
  const active = isActiveJob(job)
  const target = jobTarget(job)
  const took = elapsed(job.started_at, job.ended_at)
  return (
    <Card size="sm" aria-label={`Job ${jobTitle(job)}`}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
          <JobBadge state={job.state} />
          <span>{jobTitle(job)}</span>
          <Badge variant="outline" title={job.lane === "model" ? "calls a model: one model job at a time" : "no model call"}>{job.lane}</Badge>
        </CardTitle>
        <CardDescription className="text-xs">
          <Link to={`/jobs/${job.id}`} className="font-mono hover:underline">{job.id}</Link> · started {dateTime(job.started_at ?? job.created_at)}
          {took !== null && ` · ${duration(took)}`}
          {job.state === "queued" && job.lane === "model" && " · waits for the model job ahead of it"}
          {job.error && ` · ${job.error}`}
          {job.warnings.length > 0 && ` · ${job.warnings.join("; ")}`}
        </CardDescription>
        <CardAction className="flex gap-1">
          {target && (
            <Button size="xs" variant="outline" onClick={() => navigate(target)}>
              <ExternalLinkIcon data-icon="inline-start" />
              Open
            </Button>
          )}
          {active && (
            <Button size="xs" variant="outline" disabled={cancel.isPending}
              onClick={() => cancel.mutate(job.id, { onError: (e) => announceError("Cancel failed", e) })}>
              <SquareIcon data-icon="inline-start" />
              Cancel
            </Button>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-2">
        {!compact && (
          <ol className="space-y-1 text-xs">
            {job.steps.map((s, n) => (
              <li key={n} className="flex min-w-0 items-start gap-2">
                <JobBadge state={s.state === "pending" ? "queued" : s.state === "skipped" ? "failed" : s.state} />
                <span className="shrink-0 font-medium">{s.name}{s.state === "skipped" ? " (skipped)" : ""}</span>
                <code className="min-w-0 truncate text-muted-foreground" title={s.command}>{s.command}</code>
              </li>
            ))}
          </ol>
        )}
        <JobLog job={job} lines={compact ? 12 : 200} />
      </CardContent>
    </Card>
  )
}
