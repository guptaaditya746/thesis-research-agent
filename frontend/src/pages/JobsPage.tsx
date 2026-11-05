/**
 * Jobs `/jobs` and `/jobs/:jobId`: every job the app started (state kept in $EV/.jobs, so a reload or a
 * restarted server still lists them), newest first, with status, lane, cancel and the log; one job opened in
 * full. The list polls while a job is queued or running.
 */
import { ActivityIcon } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"

import { isActiveJob, useJob, useJobs } from "@/api/ev"
import { JobBadge } from "@/components/badges"
import { QueryPage } from "@/components/ev/bits"
import { JobPanel } from "@/components/jobs/JobPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, elapsed } from "@/lib/format"
import { jobTitle } from "@/lib/jobs"
import { cn } from "@/lib/utils"

function JobDetail({ id }: { id: string }) {
  const job = useJob(id)
  return (
    <QueryPage query={job} what={`job ${id}`} back={{ to: "/jobs", label: "All jobs" }}>
      {(data) => <JobPanel job={data} />}
    </QueryPage>
  )
}

/** Rows shown until "show all": $EV/.jobs only grows, and a long table hides the jobs that matter (the newest). */
const LIMIT = 50

/** Columns shown from a breakpoint up only, so a phone sees the state and the job without scrolling sideways. */
const NARROW_HIDDEN: Partial<Record<string, string>> = {
  lane: "hidden sm:table-cell", started: "hidden md:table-cell", took: "hidden sm:table-cell", id: "hidden lg:table-cell",
}

export default function JobsPage() {
  const { jobId } = useParams()
  const jobs = useJobs()
  const [all, setAll] = useState(false)
  const active = jobs.data?.filter(isActiveJob) ?? []
  return (
    <div className="space-y-6">
      <PageHeader title="Jobs" description={<>What the app started, from the flow: template corpora, engine runs, baselines, scores, the proposal flow. Model jobs run one at a time, the others beside them. State and logs in <span className="font-mono">$EV/.jobs</span>.</>} />
      {jobId && <JobDetail id={jobId} />}
      {!jobId && active.length > 0 && (
        <section aria-labelledby="jobs-running" className="space-y-2">
          <h2 id="jobs-running" className="text-base font-semibold">Running now</h2>
          {active.map((j) => <JobPanel key={j.id} job={j} compact />)}
        </section>
      )}
      <h2 className="text-base font-semibold">{jobId ? "All jobs" : "Every job, newest first"}</h2>
      {jobs.isPending ? <TableSkeleton /> : jobs.isError ? <ErrorState error={jobs.error} onRetry={() => void jobs.refetch()} /> : jobs.data.length === 0 ? (
        <EmptyState icon={<ActivityIcon />} title="No jobs yet" description="Start one from a question's flow." />
      ) : (
        <div className="overflow-auto rounded-md border">
          <Table aria-label="Jobs">
            <TableHeader>
              <TableRow>
                {/* on a phone: state and job (the job opens from its name); the rest from sm/md up */}
                {["state", "job", "lane", "started", "took", "id"].map((h) => <TableHead key={h} className={cn("text-xs", NARROW_HIDDEN[h])}>{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {(all ? jobs.data : jobs.data.slice(0, LIMIT)).map((j) => (
                <TableRow key={j.id} data-state={j.id === jobId ? "selected" : undefined}>
                  <TableCell><JobBadge state={j.state} failedCalls={j.failed_calls} /></TableCell>
                  <TableCell className="min-w-40 text-sm whitespace-normal">
                    <Link to={`/jobs/${j.id}`} aria-current={j.id === jobId ? "page" : undefined} className="inline-flex min-h-6 items-center underline-offset-2 hover:underline">{jobTitle(j)}</Link>
                    {j.error ? <span className="text-muted-foreground"> · {j.error}</span> : null}
                  </TableCell>
                  <TableCell className={NARROW_HIDDEN.lane}><Badge variant="outline">{j.lane}</Badge></TableCell>
                  <TableCell className={cn("text-xs", NARROW_HIDDEN.started)}>{dateTime(j.started_at ?? j.created_at)}</TableCell>
                  <TableCell className={cn("text-xs tabular-nums", NARROW_HIDDEN.took)}>{duration(elapsed(j.started_at, j.ended_at))}</TableCell>
                  <TableCell className={cn("font-mono text-xs text-muted-foreground", NARROW_HIDDEN.id)}>{j.id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!all && jobs.data.length > LIMIT && (
            <div className="flex flex-wrap items-center gap-2 border-t p-2 text-xs text-muted-foreground">
              The latest {LIMIT} of {jobs.data.length}.
              <Button size="sm" variant="outline" onClick={() => setAll(true)}>Show all {jobs.data.length}</Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
