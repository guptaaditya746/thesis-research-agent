/**
 * Jobs `/jobs` and `/jobs/:jobId`: every job the app started (state kept in $EV/.jobs, so a reload or a
 * restarted server still lists them), newest first, with status, lane, cancel and the log; one job opened in
 * full. The list polls while a job is queued or running.
 */
import { ActivityIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { isActiveJob, useJob, useJobs } from "@/api/ev"
import { JobBadge } from "@/components/badges"
import { QueryPage } from "@/components/ev/bits"
import { JobPanel } from "@/components/jobs/JobPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, elapsed } from "@/lib/format"
import { jobTitle } from "@/lib/jobs"

function JobDetail({ id }: { id: string }) {
  const job = useJob(id)
  return (
    <QueryPage query={job} what={`job ${id}`} back={{ to: "/jobs", label: "All jobs" }}>
      {(data) => <JobPanel job={data} />}
    </QueryPage>
  )
}

export default function JobsPage() {
  const { jobId } = useParams()
  const jobs = useJobs()
  const active = jobs.data?.filter(isActiveJob) ?? []
  return (
    <div className="space-y-6">
      <PageHeader title="Jobs" description={<>What the app started, from the flow: template corpora, engine runs, baselines, scores, the proposal flow. Model jobs run one at a time, the others beside them. State and logs in <span className="font-mono">$EV/.jobs</span>.</>} />
      {jobId && <JobDetail id={jobId} />}
      {!jobId && active.map((j) => <JobPanel key={j.id} job={j} compact />)}
      {jobs.isPending ? <TableSkeleton /> : jobs.isError ? <ErrorState error={jobs.error} onRetry={() => void jobs.refetch()} /> : jobs.data.length === 0 ? (
        <EmptyState icon={<ActivityIcon />} title="No jobs yet" description="Start one from a question's flow." />
      ) : (
        <div className="overflow-auto rounded-md border">
          <Table aria-label="Jobs">
            <TableHeader>
              <TableRow>
                {["state", "job", "lane", "started", "took", "id"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.data.map((j) => (
                <TableRow key={j.id} data-state={j.id === jobId ? "selected" : undefined}>
                  <TableCell><JobBadge state={j.state} failedCalls={j.failed_calls} /></TableCell>
                  <TableCell className="text-sm">{jobTitle(j)}{j.error ? <span className="text-muted-foreground"> · {j.error}</span> : null}</TableCell>
                  <TableCell><Badge variant="outline">{j.lane}</Badge></TableCell>
                  <TableCell className="text-xs">{dateTime(j.started_at ?? j.created_at)}</TableCell>
                  <TableCell className="text-xs tabular-nums">{duration(elapsed(j.started_at, j.ended_at))}</TableCell>
                  <TableCell className="font-mono text-xs"><Link to={`/jobs/${j.id}`} className="hover:underline">{j.id}</Link></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
