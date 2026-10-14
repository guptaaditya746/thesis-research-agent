/**
 * Jobs `/jobs` and `/jobs/:jobId` (plan "Frontend pages" 8): the server's jobs (runs with their
 * attach, verify, graph and score steps; concept proposals; gold builds) and, for the selected one,
 * its steps and its live log (SSE). The list polls while a job is queued or running; a queued or
 * running job can be cancelled.
 */
import { ActivityIcon, ArrowDownToLineIcon, CircleCheckIcon, CircleDashedIcon, CircleXIcon, Loader2Icon, RotateCwIcon, SkipForwardIcon, SquareIcon } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"

import { isActiveJob, useCancelJob, useJob, useJobs } from "@/api/hooks"
import { useJobLog } from "@/api/stream"
import type { Job, JobStep } from "@/api/types"
import { JobBadge, LiveDot } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, elapsed } from "@/lib/format"
import { splitRunId } from "@/lib/run"
import { announceError } from "@/lib/toasts"
import { cn } from "@/lib/utils"

function argsText(args: Job["args"]): string {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined && v !== false)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" ")
}

export default function JobsPage() {
  const { jobId } = useParams()
  const jobs = useJobs()
  const navigate = useNavigate()
  const selected = jobId ?? null

  return (
    <div className="flex h-[calc(100svh-7rem)] min-h-[32rem] flex-col gap-4">
      <PageHeader title="Jobs" description="Work the server runs for the app, one job of a kind at a time: agent runs with their attach, verify, graph and score steps, concept proposals and gold builds." />
      {jobs.isError ? (
        <ErrorState error={jobs.error} onRetry={() => void jobs.refetch()} />
      ) : jobs.isPending ? (
        <TableSkeleton rows={6} columns={5} />
      ) : jobs.data.length === 0 ? (
        <EmptyState icon={<ActivityIcon />} title="No jobs yet" description="Starting a run, proposing concepts or building a gold standard creates a job here." />
      ) : (
        <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1 rounded-lg border">
          <ResizablePanel defaultSize="50%" minSize="30%">
            <div className="h-full overflow-auto">
              <Table>
                <caption className="sr-only">Jobs</caption>
                <TableHeader className="sticky top-0 z-10 bg-background">
                  <TableRow>
                    <TableHead className="pl-4">Job</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Took</TableHead>
                    <TableHead className="pr-4">Run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.data.map((j) => (
                    <TableRow
                      key={j.id}
                      data-state={selected === j.id ? "selected" : undefined}
                      className="cursor-pointer"
                      onClick={() => navigate(`/jobs/${j.id}`)}
                    >
                      <TableCell className="pl-4">
                        <Link to={`/jobs/${j.id}`} className="font-mono text-xs font-medium hover:underline" onClick={(e) => e.stopPropagation()} aria-current={selected === j.id ? "page" : undefined}>
                          {j.id}
                        </Link>
                        <div className="max-w-64 truncate text-xs text-muted-foreground" title={argsText(j.args)}>
                          {j.kind}{j.qid ? ` · ${j.qid}` : ""} · {argsText(j.args)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <JobBadge state={j.state} />
                        {j.exit_code != null && j.exit_code !== 0 && <div className="mt-1 text-xs text-muted-foreground">exit {j.exit_code}</div>}
                        {!!j.warnings?.length && <div className="mt-1 text-xs text-status-serious">{j.warnings.length} warning{j.warnings.length === 1 ? "" : "s"}</div>}
                      </TableCell>
                      <TableCell className="text-xs whitespace-nowrap">{dateTime(j.created_at)}</TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{j.started_at ? duration(elapsed(j.started_at, j.ended_at)) : "—"}</TableCell>
                      <TableCell className="pr-4 text-xs">
                        {j.run_id ? (
                          <Link to={`/runs/${encodeURIComponent(j.run_id)}`} className="font-mono break-all hover:underline" onClick={(e) => e.stopPropagation()}>
                            {splitRunId(j.run_id).name}
                          </Link>
                        ) : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize="50%" minSize="25%">
            {selected ? (
              <JobLog key={selected} jobId={selected} />
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">Select a job to follow its steps and log.</div>
            )}
          </ResizablePanel>
        </ResizablePanelGroup>
      )}
    </div>
  )
}

const STEP_ICON = {
  pending: <CircleDashedIcon className="text-muted-foreground" />,
  running: <Loader2Icon className="animate-spin text-muted-foreground motion-reduce:animate-none" />,
  done: <CircleCheckIcon className="text-status-good" />,
  failed: <CircleXIcon className="text-status-critical" />,
  skipped: <SkipForwardIcon className="text-muted-foreground" />,
}

function JobSteps({ steps }: { steps: JobStep[] }) {
  if (!steps.length) return null
  return (
    <ol className="flex flex-wrap gap-x-3 gap-y-1 border-b px-3 py-2 text-xs" aria-label="Steps of the job">
      {steps.map((s) => {
        const state = s.state ?? "pending"
        return (
          <li key={s.name} className="flex items-center gap-1 [&>svg]:size-3.5" title={`${s.command}${s.required === false ? " (optional)" : ""}`}>
            {STEP_ICON[state]}
            <span className={cn(state === "skipped" && "text-muted-foreground line-through")}>{s.name}</span>
            <span className="sr-only">{state}</span>
            {s.exit_code != null && s.exit_code !== 0 && <span className="text-muted-foreground">exit {s.exit_code}</span>}
          </li>
        )
      })}
    </ol>
  )
}

function JobLog({ jobId }: { jobId: string }) {
  const job = useJob(jobId)
  const cancel = useCancelJob()
  const { lines, status, reconnect } = useJobLog(jobId, !job.isError)
  const [follow, setFollow] = useState(true)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (follow) end.current?.scrollIntoView({ block: "end" })
  }, [lines.length, follow])

  const j = job.data
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2 text-sm">
        <span className="font-mono font-medium">{jobId}</span>
        {j ? <JobBadge state={j.state} /> : job.isPending ? <Skeleton className="h-5 w-16" /> : null}
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
          {status === "open" && <LiveDot />}
          {status === "open" ? "streaming" : status === "done" ? "end of log" : status === "error" ? "stream closed" : status}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {j && isActiveJob(j) && (
            <Button
              size="xs"
              variant="outline"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate(j.id, { onError: (error) => announceError(`Could not cancel ${j.id}`, error) })}
            >
              <SquareIcon data-icon="inline-start" /> Cancel
            </Button>
          )}
          <Switch id="log-follow" checked={follow} onCheckedChange={setFollow} />
          <Label htmlFor="log-follow" className="text-xs"><ArrowDownToLineIcon className="size-3.5" aria-hidden="true" /> Follow</Label>
          {(status === "error" || status === "done") && (
            <Button size="xs" variant="outline" onClick={reconnect}>
              <RotateCwIcon data-icon="inline-start" /> Replay
            </Button>
          )}
        </div>
      </div>
      {j && <JobSteps steps={j.steps ?? []} />}
      {j?.error && <p className="border-b px-3 py-2 text-xs text-destructive" role="alert">{j.error}</p>}
      {!!j?.warnings?.length && (
        <ul className="border-b px-3 py-2 text-xs text-status-serious">
          {j.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
      {job.isError ? (
        <div className="p-3"><ErrorState error={job.error} /></div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto bg-muted/30 p-3" role="log" aria-label={`Log of ${jobId}`} aria-live="polite">
          {lines.length === 0 && status !== "done" ? (
            <p className="text-xs text-muted-foreground">Waiting for log lines…</p>
          ) : (
            <pre className="font-mono text-xs leading-relaxed whitespace-pre-wrap">
              {lines.map((line, i) => (
                <div key={i} className={cn(line.startsWith("$ ") && "font-semibold", /error|failed|exit [1-9]/i.test(line) && "text-destructive")}>
                  {line}
                </div>
              ))}
            </pre>
          )}
          <div ref={end} />
        </div>
      )}
    </div>
  )
}
