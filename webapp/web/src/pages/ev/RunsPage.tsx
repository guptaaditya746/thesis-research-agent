/**
 * Runs `/runs`: every engine run (`evidence run`: the selection regex-only / cascade, the strategy all /
 * gaps) and every baseline answer (`evaluate rag-baseline`, `agent-baseline`), grouped by corpus so the
 * engine sits beside the baselines on the same papers. Label, counts and cost per run.
 */
import { FlaskConicalIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { useEvRuns } from "@/api/ev"
import { ErrorCallsBadge } from "@/components/badges"
import { LabelBadge, SystemBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { runsByCorpus, systemOrder } from "@/lib/ev"
import { tokens } from "@/lib/format"

export default function RunsPage() {
  const runs = useEvRuns()
  const [showHistory, setShowHistory] = useState(false)
  const history = (runs.data ?? []).filter((r) => r.mode === "replay" || r.mode === "reexec")
  const visibleRuns = (runs.data ?? []).filter((r) => showHistory || (r.mode !== "replay" && r.mode !== "reexec"))
  const groups = [...runsByCorpus(visibleRuns).entries()].sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="space-y-6">
      <PageHeader title="Runs" description="Main runs and baseline answers, grouped by corpus. Replay and re-execution history is optional." />
      <div className="flex w-fit items-center gap-2">
        <Switch id="runs-history" checked={showHistory} onCheckedChange={setShowHistory} />
        <Label htmlFor="runs-history" className="font-normal text-muted-foreground">Show replay and re-execution history ({history.length})</Label>
      </div>
      {runs.isPending && <TableSkeleton />}
      {runs.isError && <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />}
      {runs.data && !runs.data.length && (
        <EmptyState icon={<FlaskConicalIcon />} title="No runs" description="Nothing under the runs root ($EV_RUNS, default $EV/runs). `uv run evidence run --protocol P --corpus C --out $EV/runs/<group>`." />
      )}
      {groups.map(([corpus, list]) => (
        <section key={corpus} className="space-y-2">
          <h2 className="font-mono text-sm font-semibold">
            {list[0]?.corpus ? <Link to={`/corpora/${encodeURIComponent(corpus)}`} className="hover:underline">{corpus}</Link> : corpus}
          </h2>
          <div className="overflow-auto rounded-md border">
            <Table aria-label={`Runs on ${corpus}`}>
              <TableHeader>
                <TableRow>
                  {["run", "system", "selection", "strategy", "label", "counts (+ / − / 0 / ?)", "calls", "tokens", "seconds"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...list].sort((a, b) => systemOrder(a.system, b.system) || a.group.localeCompare(b.group)).map((r) => {
                  const cost = (r.cost ?? {}) as Record<string, number | undefined>
                  const c = r.counts
                  return (
                    <TableRow key={r.id}>
                      <TableCell className="font-mono text-xs"><Link to={`/runs/${encodeURIComponent(r.id)}`} className="hover:underline">{r.group}</Link>{r.mode && r.mode !== "run" && <Badge variant="outline" className="ml-1">{r.mode}</Badge>}{!r.complete && <Badge variant="destructive" className="ml-1" title="no run.json: crashed or still running">incomplete</Badge>}</TableCell>
                      <TableCell><SystemBadge system={r.system} /></TableCell>
                      <TableCell className="text-xs">{r.selection ?? "—"}</TableCell>
                      <TableCell className="text-xs">{r.strategy ?? "—"}</TableCell>
                      <TableCell><LabelBadge label={r.label} /> <ErrorCallsBadge count={r.error_calls} /></TableCell>
                      <TableCell className="font-mono text-xs tabular-nums">{c ? `${c.supporting ?? 0} / ${c.contradicting ?? 0} / ${c.neutral ?? 0} / ${c.undetermined ?? 0}` : "—"}</TableCell>
                      <TableCell className="text-xs tabular-nums">{cost.calls ?? "—"}</TableCell>
                      <TableCell className="text-xs tabular-nums">{cost.input_tokens === undefined ? "—" : tokens((cost.input_tokens ?? 0) + (cost.output_tokens ?? 0))}</TableCell>
                      <TableCell className="text-xs tabular-nums">{cost.seconds ?? "—"}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </section>
      ))}
    </div>
  )
}
