/**
 * Results `/results` (plan "Frontend pages" 6): the pre-registered primary test first, then the
 * measures by condition with their BCa intervals (support share, F1, unsourced share; tokens and
 * time with and without the attach step, each on its own chart: one axis per chart), the
 * per-question table (the charts' table view) and the paired tests.
 */
import { BarChart3Icon, CheckCircle2Icon, CircleMinusIcon } from "lucide-react"
import type { ReactNode } from "react"

import { useResults } from "@/api/hooks"
import type { MetricName, ResultsReport } from "@/api/types"
import { StatusBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ConditionChart } from "@/components/results/ConditionChart"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, num, pct, pp, pValue, tokens } from "@/lib/format"
import { costGroups, METRIC_LABEL, metricGroups, questionRows } from "@/lib/results"

const share = (v: number) => `${Math.round(v * 100)}%`

export default function ResultsPage() {
  const results = useResults()
  return (
    <div className="space-y-6">
      <PageHeader
        title="Results"
        description="claim on vs claim off after attach, paired over the 12 questions (mean of 3 repeats per question and condition)."
      />
      {results.isPending ? (
        <CardsSkeleton count={4} className="xl:grid-cols-2" />
      ) : results.isError ? (
        <ErrorState error={results.error} onRetry={() => void results.refetch()} />
      ) : !results.data ? (
        <EmptyState
          icon={<BarChart3Icon />}
          title="No report yet"
          description="$RUNS/report/report.json is written by `score report` once the runs are scored against the keys."
        />
      ) : (
        <Report report={results.data} />
      )}
    </div>
  )
}

function Report({ report }: { report: ResultsReport }) {
  const supportRows = metricGroups(report, ["support_share"])
  const f1Rows = metricGroups(report, ["fact_f1", "row_f1", "vital_recall"])
  const unsourcedRows = metricGroups(report, ["unsourced_share"])
  const tokenRows = costGroups(report, "tokens").map((g) => ({ label: g.measure, claim_on: g.claim_on, claim_off: g.claim_off }))
  const timeRows = costGroups(report, "seconds").map((g) => ({ label: g.measure, claim_on: g.claim_on, claim_off: g.claim_off }))

  return (
    <>
      <p className="text-xs text-muted-foreground">
        Report of {dateTime(report.generated_at)} · key {report.key_version ?? "?"} · {report.n_questions} questions × {report.repeats} repeats
      </p>
      <PrimaryTest report={report} />
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Support share" description="Share of answer facts whose quote supports them (judge). Bars: mean over questions; whiskers: 95% BCa interval.">
          <ConditionChart label="Support share by condition" data={supportRows} format={share} domain={[0, 1]} />
        </ChartCard>
        <ChartCard title="F1 against the key" description="Soft fact F1, row F1 and vital recall, with 95% intervals.">
          <ConditionChart label="Fact F1, row F1 and vital recall by condition" data={f1Rows} format={(v) => v.toFixed(2)} domain={[0, 1]} />
        </ChartCard>
        <ChartCard title="Unsourced share" description="Share of answer facts with no claim behind them, with 95% intervals.">
          <ConditionChart label="Unsourced share by condition" data={unsourcedRows} format={share} domain={[0, 1]} />
        </ChartCard>
        <ChartCard title="Tokens per run" description="Mean tokens; “without attach” leaves out the baseline's attach step.">
          <ConditionChart label="Tokens with and without attach by condition" data={tokenRows} format={tokens} />
        </ChartCard>
        <ChartCard title="Time per run" description="Mean wall time, with and without the attach step.">
          <ConditionChart label="Time with and without attach by condition" data={timeRows} format={(v) => duration(v)} />
        </ChartCard>
        <PairedTests report={report} />
      </div>
      <PerQuestion report={report} />
    </>
  )
}

function ChartCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function PrimaryTest({ report }: { report: ResultsReport }) {
  const p = report.primary
  if (!p) {
    return <EmptyState title="The primary test has not been computed" description="report.json has no `primary` section yet." />
  }
  return (
    <Card className="border-2">
      <CardHeader>
        <CardDescription>Pre-registered primary outcome</CardDescription>
        <CardTitle className="text-lg leading-snug">{p.hypothesis}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <p className="text-xs text-muted-foreground">Mean difference (claim on − claim off)</p>
            <p className="text-4xl font-semibold">{pp(p.mean_difference)}</p>
            {p.ci && (
              <p className="text-sm text-muted-foreground tabular-nums">
                {Math.round((p.ci.level ?? 0.95) * 100)}% {p.ci.method ?? "BCa"} interval [{pp(p.ci.low)}, {pp(p.ci.high)}]
              </p>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <div><dt className="text-muted-foreground">Test</dt><dd>{p.test}, {p.alternative}</dd></div>
            <div><dt className="text-muted-foreground">n (questions)</dt><dd className="tabular-nums">{p.n}</dd></div>
            <div><dt className="text-muted-foreground">W</dt><dd className="tabular-nums">{num(p.wilcoxon?.statistic ?? null, 1)}</dd></div>
            <div><dt className="text-muted-foreground">p (α = {p.alpha})</dt><dd className="tabular-nums">{pValue(p.wilcoxon?.p_value)}</dd></div>
          </dl>
          {p.significant === null ? null : p.significant ? (
            <StatusBadge tone="good" icon={<CheckCircle2Icon />}>significant at α = {p.alpha}</StatusBadge>
          ) : (
            <StatusBadge tone="neutral" icon={<CircleMinusIcon />}>not significant at α = {p.alpha}</StatusBadge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">Metric: {METRIC_LABEL[p.metric] ?? p.metric}.</p>
      </CardContent>
    </Card>
  )
}

function PairedTests({ report }: { report: ResultsReport }) {
  const tests = Object.values(report.paired).filter((t) => !!t)
  const isShare = (m: MetricName) => m.endsWith("share") || m.includes("f1") || m.includes("recall") || m.includes("precision")
  return (
    <ChartCard title="Paired tests" description="Secondary measures: Wilcoxon signed-rank over the questions, mean difference with its interval.">
      {tests.length === 0 ? (
        <p className="text-sm text-muted-foreground">No paired tests in the report.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Measure</TableHead>
              <TableHead className="text-right">Δ mean</TableHead>
              <TableHead className="text-right">95% interval</TableHead>
              <TableHead className="text-right">p</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tests.map((t) => {
              const f = (v: number | null | undefined) => (isShare(t.metric) ? pp(v) : tokens(v))
              return (
                <TableRow key={t.metric}>
                  <TableCell>{METRIC_LABEL[t.metric] ?? t.metric}</TableCell>
                  <TableCell className="text-right tabular-nums">{f(t.mean_difference)}</TableCell>
                  <TableCell className="text-right tabular-nums">{t.ci ? `[${f(t.ci.low)}, ${f(t.ci.high)}]` : "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{pValue(t.wilcoxon?.p_value)}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}
    </ChartCard>
  )
}

function PerQuestion({ report }: { report: ResultsReport }) {
  const support = questionRows(report, "support_share")
  const f1 = questionRows(report, "fact_f1")
  const unsourced = questionRows(report, "unsourced_share")
  const tok = questionRows(report, "tokens")
  return (
    <Card>
      <CardHeader>
        <CardTitle>Per question</CardTitle>
        <CardDescription>Means over the repeats; Δ = claim on − claim off. The values behind every chart above.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Question</TableHead>
              <TableHead className="text-right">Runs on / off</TableHead>
              <TableHead className="text-right">Support on</TableHead>
              <TableHead className="text-right">Support off</TableHead>
              <TableHead className="text-right">Δ support</TableHead>
              <TableHead className="text-right">F1 on / off</TableHead>
              <TableHead className="text-right">Unsourced on / off</TableHead>
              <TableHead className="text-right">Tokens on / off</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {support.map((row, i) => (
              <TableRow key={row.qid}>
                <TableCell>
                  <span className="font-mono">{row.qid}</span>{" "}
                  <Badge variant="secondary" className="ml-1 font-normal">{row.category.replace("_", " ")}</Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">{row.runs}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(row.on)}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(row.off)}</TableCell>
                <TableCell className="text-right font-medium tabular-nums">{pp(row.diff)}</TableCell>
                <TableCell className="text-right tabular-nums">{num(f1[i]?.on)} / {num(f1[i]?.off)}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(unsourced[i]?.on, 0)} / {pct(unsourced[i]?.off, 0)}</TableCell>
                <TableCell className="text-right tabular-nums">{tokens(tok[i]?.on)} / {tokens(tok[i]?.off)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
