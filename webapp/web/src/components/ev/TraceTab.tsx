/**
 * The run page's "Developer tools" tab: one row per step the run took (a warm-pass call or an engine event),
 * filled in as the run writes it. Filter by paper and by status; a row with a call opens the call sheet with
 * the full prompt and reply (a skipped extractor call has none: the backend gives it no call).
 */
import { useState } from "react"

import { useActiveJobs, useTrace } from "@/api/ev"
import { CallSheet } from "@/components/ev/CallSheet"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DASH, int, num } from "@/lib/format"

const SELECT = "h-8 rounded-md border bg-background px-2 text-sm"

/** ISO time -> local HH:MM:SS; none or unreadable -> "—". */
function clock(iso: string | null | undefined): string {
  const d = iso ? new Date(iso) : null
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString("en-GB") : DASH
}

export function TraceTab({ runId }: { runId: string }) {
  const live = useActiveJobs({ run: runId }).length > 0
  const trace = useTrace(runId, live)
  const [paper, setPaper] = useState("")
  const [status, setStatus] = useState("")
  const [call, setCall] = useState<string | null>(null)
  if (trace.isPending) return <CardsSkeleton count={1} />
  if (!trace.data) return <ErrorState error={trace.error} />   // failed before any rows arrived
  const all = trace.data.rows
  const papers = [...new Set(all.map((r) => r.document).filter((d): d is string => !!d))].sort()
  const statuses = [...new Set(all.map((r) => r.status))].sort()
  const rows = all.filter((r) => (!paper || r.document === paper) && (!status || r.status === status))
  return (
    <div className="space-y-3">
      {trace.isError && <p role="alert" className="text-sm text-destructive">The latest poll failed ({trace.error.message}); showing the rows read so far.</p>}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">Paper
          <select aria-label="Paper" className={SELECT} value={paper} onChange={(e) => setPaper(e.target.value)}>
            <option value="">all</option>
            {papers.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">Status
          <select aria-label="Status" className={SELECT} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">all</option>
            {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <span className="text-muted-foreground">{rows.length} of {all.length} steps{trace.data.done ? "" : " (the run is still going)"}</span>
      </div>
      <div className="overflow-auto rounded-md border">
        <Table aria-label="Run trace">
          <TableHeader>
            <TableRow>
              {["#", "time", "phase", "step", "paper", "type", "extractor", "status", "seconds", "tokens"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.n} className={r.call ? "cursor-pointer" : undefined}
                onClick={r.call ? () => setCall(r.call) : undefined}>
                <TableCell className="text-xs tabular-nums">{r.n}</TableCell>
                <TableCell className="text-xs tabular-nums">{clock(r.at)}</TableCell>
                <TableCell className="text-xs">{r.phase}</TableCell>
                <TableCell className="font-mono text-xs">
                  {r.call ? <Button variant="link" size="sm" className="h-auto p-0 font-mono text-xs" onClick={(e) => { e.stopPropagation(); setCall(r.call) }}>{r.step}</Button> : r.step}
                </TableCell>
                <TableCell className="font-mono text-xs">{r.document ?? DASH}</TableCell>
                <TableCell className="text-xs">{r.evidence_type ?? DASH}</TableCell>
                <TableCell className="text-xs">{r.extractor ?? DASH}</TableCell>
                {/* a skipped extractor call: its service (GLiNER) was unavailable, so there is no call to open */}
                <TableCell className="text-xs">{r.step === "extractor_call" && r.status === "skipped" ? "skipped: service unavailable" : r.status}</TableCell>
                <TableCell className="text-xs tabular-nums">{r.seconds === null ? DASH : `${num(r.seconds, 1)} s`}</TableCell>
                <TableCell className="text-xs tabular-nums">
                  {r.input_tokens === null && r.output_tokens === null ? DASH : `${int(r.input_tokens)} / ${int(r.output_tokens)}`}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <CallSheet runId={runId} callId={call} onClose={() => setCall(null)} />
    </div>
  )
}
