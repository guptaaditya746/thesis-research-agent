/**
 * The Report `/report`: every run's scores in one place (it replaces the old Scores page).
 *
 * - First, per domain, the questions with the engine's losses first (losses.json of `evaluate losses`): each
 *   system's headline score, and for each loss one line saying why it lost; beside it the model calls and
 *   tokens each system spent. The comparison opens with the supervisor's caution.
 * - Below, what `evaluate` wrote under the scores root, as the Scores page listed it: the per-run reports
 *   (A, B, C per level), the comparisons, the shifts of a controlled variant and the benchmark records.
 */
import { BarChart3Icon } from "lucide-react"
import { Link } from "react-router"

import { useLosses, useScores, type LossRow, type ScoreRef, type SystemCost } from "@/api/ev"
import { JsonBlock, RowsTable, SystemBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { evCell, systemLabel, systemOrder } from "@/lib/ev"

const reportHref = (kind: string, id: string) => `/report/${kind}/${encodeURIComponent(id)}`

/** Why the engine lost, in plain words (evaluation/losses.py CAUSES). */
const CAUSE_TEXT: Record<string, string> = {
  missed: "the engine did not find values the answer needs",
  "wrongly linked": "values were linked to the wrong study, condition or metric",
  "names not grouped": "names for the same thing were not grouped together",
  "wrong rule": "the values were right; the rule that turns them into the answer was not",
}

const CAUTION = "We should not assume that the evidence-level approach will necessarily perform better"

const COST_FIELDS = ["model_calls", "input_tokens", "output_tokens", "tokens"] as const

/** Model calls and tokens per system over the rows: a sum, or null when a row does not report that count. */
function costPerSystem(rows: LossRow[], systems: string[]): Record<string, unknown>[] {
  return systems.map((system) => {
    const costs = rows.map((r) => r.cost[system]).filter((c): c is SystemCost => !!c)
    const total = (field: (typeof COST_FIELDS)[number]) =>
      costs.length && costs.every((c) => c[field] != null) ? costs.reduce((sum, c) => sum + (c[field] ?? 0), 0) : null
    return { system, questions: costs.length, ...Object.fromEntries(COST_FIELDS.map((f) => [f, total(f)])) }
  })
}

function DomainLosses({ domain, rows }: { domain: string; rows: LossRow[] }) {
  const systems = [...new Set(rows.flatMap((r) => Object.keys(r.systems)))].sort(systemOrder)
  return (
    <section aria-label={`Losses in ${domain}`} className="space-y-3">
      <h3 className="text-sm font-semibold">{domain}</h3>
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">No questions scored in this domain.</p> : (
        <>
          <div className="overflow-auto rounded-md border">
            <Table aria-label="Questions, losses first">
              <TableHeader>
                <TableRow>
                  {["question", "kind", ...systems.map(systemLabel), "engine lost", "why", "report"].map((h) => <TableHead key={h} className="text-xs whitespace-nowrap">{h}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={`${r.question_id}~${r.report}`}>
                    <TableCell className="font-mono text-xs">{r.question_id}</TableCell>
                    <TableCell className="text-xs">{r.kind}</TableCell>
                    {systems.map((s) => <TableCell key={s} className="text-xs tabular-nums">{evCell(r.systems[s])}</TableCell>)}
                    <TableCell className="text-xs">{r.engine_loss ? <Badge variant="destructive">lost</Badge> : "no"}</TableCell>
                    <TableCell className="max-w-96 text-xs">{r.cause ? <><span className="font-medium">{r.cause}</span>: {CAUSE_TEXT[r.cause] ?? ""}</> : "—"}</TableCell>
                    <TableCell className="font-mono text-xs"><Link to={reportHref("reports", r.report)} className="hover:underline">{r.report.replace("~", " / ")}</Link></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <RowsTable caption="Model calls and tokens per system" rows={costPerSystem(rows, systems)} columns={["system", "questions", ...COST_FIELDS]}
            render={(c, v) => (c === "system" ? <SystemBadge system={String(v)} /> : evCell(v))} />
        </>
      )}
    </section>
  )
}

function Losses() {
  const losses = useLosses()
  if (losses.isPending) return <TableSkeleton />
  if (losses.isError) return <ErrorState error={losses.error} onRetry={() => void losses.refetch()} />
  const { losses: table, markdown } = losses.data
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Questions, losses first</h2>
      <blockquote className="border-l-2 pl-3 text-sm italic text-muted-foreground">“{CAUTION}.” (the supervisor)</blockquote>
      {table ? Object.entries(table.domains).sort(([a], [b]) => a.localeCompare(b)).map(([domain, rows]) => <DomainLosses key={domain} domain={domain} rows={rows} />)
        : <p className="text-sm text-muted-foreground">No losses table yet: <span className="font-mono">uv run evaluate losses --scores $EV/scores --out $EV/scores/losses</span>.</p>}
      {markdown && <details><summary className="cursor-pointer text-sm">losses.md</summary><JsonBlock value={markdown} className="mt-1 max-h-[60vh]" /></details>}
    </section>
  )
}

function RefList({ title, refs, kind, describe }: { title: string; refs: ScoreRef[]; kind: string; describe: (r: ScoreRef) => string }) {
  if (!refs.length) return null
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold">{title}</h2>
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {refs.map((r) => (
          <li key={r.id}>
            <Link to={reportHref(kind, r.id)} className="block rounded-md border p-3 text-sm hover:bg-muted">
              <span className="font-mono text-xs">{r.id.replace("~", " / ")}</span>
              <span className="block text-xs text-muted-foreground">{describe(r)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function ReportsPage() {
  const scores = useScores()
  const data = scores.data
  const empty = data && !data.reports.length && !data.compares.length && !data.shifts.length && !data.benchmarks.length
  return (
    <div className="space-y-6">
      <PageHeader title="Report" description="Every run's scores: the questions the engine lost first, with why and what each system spent; then A extraction, B integration, C synthesis per difficulty level against the ground truth, the engine beside the baselines, with 95 % intervals over papers." />
      <Losses />
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
                    <TableCell className="font-mono text-xs"><Link to={reportHref("reports", r.id)} className="hover:underline">{r.group}</Link></TableCell>
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
          <RefList title="Comparisons" refs={data.compares} kind="compares" describe={(r) => (r.group.startsWith("compare-funnel") ? "all against gaps on one corpus" : "over corpora, per level")} />
          <RefList title="Shift of a controlled variant" refs={data.shifts} kind="shifts" describe={(r) => `${r.systems.length} system(s) scored on both`} />
          <RefList title="Benchmark records" refs={data.benchmarks} kind="benchmarks" describe={(r) => `${r.systems.length} extractor(s)`} />
        </>
      )}
    </div>
  )
}
