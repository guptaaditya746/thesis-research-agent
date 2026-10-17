/**
 * Scores `/scores`: everything `evaluate` wrote under the scores root. Reports (`evaluate score`: A, B, C per
 * level with intervals, one per selection and corpus), comparisons (`evaluate compare`: over corpora, or
 * all against gaps on one corpus), shifts (`evaluate shift`: the controlled variant) and benchmark records
 * (`evaluate benchmark`: per extractor).
 */
import { BarChart3Icon } from "lucide-react"
import { Link } from "react-router"

import { useScores, type ScoreRef } from "@/api/ev"
import { SystemBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

function RefList({ title, refs, kind, describe }: { title: string; refs: ScoreRef[]; kind: string; describe: (r: ScoreRef) => string }) {
  if (!refs.length) return null
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold">{title}</h2>
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {refs.map((r) => (
          <li key={r.id}>
            <Link to={`/scores/${kind}/${encodeURIComponent(r.id)}`} className="block rounded-md border p-3 text-sm hover:bg-muted">
              <span className="font-mono text-xs">{r.id.replace("~", " / ")}</span>
              <span className="block text-xs text-muted-foreground">{describe(r)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function ScoresPage() {
  const scores = useScores()
  const data = scores.data
  const empty = data && !data.reports.length && !data.compares.length && !data.shifts.length && !data.benchmarks.length
  return (
    <div className="space-y-6">
      <PageHeader title="Scores" description="A extraction, B integration, C synthesis per difficulty level, against the ground truth; the engine beside the RAG baseline and the agent baseline; 95 % BCa bootstrap intervals over papers." />
      {scores.isPending && <TableSkeleton />}
      {scores.isError && <ErrorState error={scores.error} onRetry={() => void scores.refetch()} />}
      {empty && <EmptyState icon={<BarChart3Icon />} title="No scores" description="Nothing under the scores root ($SCORES, default $EV/scores). `uv run evaluate score --run R --corpus C --out $EV/scores/<selection>/<corpus>`." />}
      {data && data.reports.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-base font-semibold">Reports</h2>
          <div className="overflow-auto rounded-md border">
            <Table aria-label="Reports">
              <TableHeader>
                <TableRow>{["selection", "corpus", "levels", "strategy", "systems"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}</TableRow>
              </TableHeader>
              <TableBody>
                {data.reports.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs"><Link to={`/scores/reports/${encodeURIComponent(r.id)}`} className="hover:underline">{r.group}</Link></TableCell>
                    <TableCell className="font-mono text-xs">{r.name ?? r.corpus_id}</TableCell>
                    <TableCell className="text-xs">{r.levels.join(", ")}</TableCell>
                    <TableCell className="text-xs">{r.strategy ? <Badge variant="outline">{r.strategy}</Badge> : "—"}</TableCell>
                    <TableCell><div className="flex flex-wrap gap-1">{r.systems.map((s) => <SystemBadge key={s} system={s} />)}</div></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}
      {data && (
        <>
          <RefList title="Comparisons" refs={data.compares} kind="compares" describe={(r) => (r.group === "compare-funnel" || r.group.startsWith("compare-funnel") ? "all against gaps on one corpus" : "over corpora, per level")} />
          <RefList title="Shift of a controlled variant" refs={data.shifts} kind="shifts" describe={(r) => `${r.systems.length} system(s) scored on both`} />
          <RefList title="Benchmark records" refs={data.benchmarks} kind="benchmarks" describe={(r) => `${r.systems.length} extractor(s)`} />
        </>
      )}
    </div>
  )
}
