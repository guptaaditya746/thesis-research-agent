/**
 * Results `/results` (plan "Frontend pages" 6): the pre-registered primary test first (with its
 * sensitivity analyses), then the outcomes by condition with their 95 % BCa intervals (support
 * share, F1, unsourced share; tokens and time with and without the attach step, each on its own
 * chart: one axis per chart), the per-question differences of the primary outcome, the secondary
 * outcomes' paired differences (intervals, no tests, as pre-registered) and the per-question
 * table, which is the charts' table view. Warnings (draft keys, pending verdicts) come first.
 */
import { BarChart3Icon, CheckCircle2Icon, CircleMinusIcon, CircleSlashIcon, FlaskConicalIcon, HourglassIcon } from "lucide-react"
import type { ReactNode } from "react"

import { useQuestions, useResults } from "@/api/hooks"
import type { Outcome, ResultsReport } from "@/api/types"
import { StatusBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ConditionChart } from "@/components/results/ConditionChart"
import { DifferenceChart } from "@/components/results/DifferenceChart"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, int, num, outcomeDifference, outcomeValue, pct, pp, pValue, tokens } from "@/lib/format"
import { conditionBars, costGroups, differences, metricGroups, pairedDifferences, questionRows, sensitivity, shareDomainMax } from "@/lib/results"

const share = (v: number) => `${Math.round(v * 100)}%`
const SECONDARY: Outcome[] = [
  "fact_precision", "fact_recall", "fact_f1", "fact_f1_normalised", "fact_f1_strict", "row_f1", "row_f1_normalised",
  "vital_recall", "judged_precision", "unsourced_share", "claims_per_fact", "tokens", "tokens_without_attach", "seconds", "seconds_without_attach",
]

export default function ResultsPage() {
  const results = useResults()
  return (
    <div className="space-y-6">
      <PageHeader
        title="Results"
        description="claim on vs claim off after attach, paired over the questions (mean of the repeats per question and condition)."
      />
      {results.isPending ? (
        <CardsSkeleton count={4} className="xl:grid-cols-2" />
      ) : results.isError ? (
        <ErrorState error={results.error} onRetry={() => void results.refetch()} />
      ) : !results.data ? (
        <EmptyState
          icon={<BarChart3Icon />}
          title="No report yet"
          description="report.json is written by `score report` once the runs are scored against the keys ($RUNS/report/, or a batch's report/)."
        />
      ) : (
        <Report report={results.data} />
      )}
    </div>
  )
}

function Report({ report }: { report: ResultsReport }) {
  const support = metricGroups(report, ["support_share"], { support_share: "support share" })
  const f1 = metricGroups(report, ["fact_f1", "row_f1", "vital_recall"], { fact_f1: "fact F1", row_f1: "row F1", vital_recall: "vital recall" })
  const unsourced = metricGroups(report, ["unsourced_share"], { unsourced_share: "unsourced share" })
  const domain = (rows: { claim_on_ci: [number, number] | null; claim_off_ci: [number, number] | null }[]): [number, number] => [
    0, shareDomainMax(rows.flatMap((r) => [r.claim_on_ci, r.claim_off_ci]).map((ci) => ({ high: ci?.[1] ?? null, mean: null }))),
  ]
  const diffs = pairedDifferences(report, "support_share")

  return (
    <>
      <Warnings report={report} />
      <p className="text-xs text-muted-foreground">
        Report of {dateTime(report.generated_at)} · {report.runs?.scored ?? "?"} scored runs · {report.questions?.length ?? 0} questions
        {report.runs_root ? <> · <span className="font-mono">{report.runs_root}</span></> : null}
        {report.settings?.interval ? ` · ${report.settings.interval}, ${report.settings.resamples ?? "?"} resamples` : ""}
      </p>
      <PrimaryTest report={report} />
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Support share" description="Share of answer facts whose quote supports them (judge). Bars: mean over questions; whiskers: 95% BCa interval.">
          <ConditionChart label="Support share by condition" data={support} format={share} domain={domain(support)} />
        </ChartCard>
        <ChartCard title="Support share, per question" description="claim on − claim off for each paired question: the differences the Wilcoxon test ranks.">
          {diffs.length ? (
            <DifferenceChart label="Difference in support share per question" data={diffs} format={(v) => pp(v, 0)} />
          ) : (
            <p className="text-sm text-muted-foreground">No question has a value in both conditions yet.</p>
          )}
        </ChartCard>
        <ChartCard title="F1 against the key" description="Soft fact F1, row F1 and vital recall, with 95% intervals.">
          <ConditionChart label="Fact F1, row F1 and vital recall by condition" data={f1} format={(v) => v.toFixed(2)} domain={domain(f1)} />
        </ChartCard>
        <ChartCard title="Unsourced share" description="Share of answer facts that cite no accepted claim, with 95% intervals.">
          <ConditionChart label="Unsourced share by condition" data={unsourced} format={share} domain={domain(unsourced)} />
        </ChartCard>
        <ChartCard title="Tokens per run" description="Mean tokens; “without attach” leaves out the baseline's attach step (claim on has none).">
          <ConditionChart label="Tokens with and without attach by condition" data={costGroups(report, "tokens")} format={tokens} />
        </ChartCard>
        <ChartCard title="Time per run" description="Mean active time, with and without the attach step.">
          <ConditionChart label="Time with and without attach by condition" data={costGroups(report, "seconds")} format={(v) => duration(v)} />
        </ChartCard>
      </div>
      <Coverage report={report} />
      <Secondary report={report} />
      <PerQuestion report={report} />
    </>
  )
}

function Warnings({ report }: { report: ResultsReport }) {
  const pending = report.completeness?.pending_support_runs ?? []
  const unverified = report.completeness?.unverified_runs ?? []
  return (
    <div className="space-y-2">
      {report.provisional && (
        <Alert className="border-status-warning/60">
          <FlaskConicalIcon className="text-status-warning" />
          <AlertTitle>Provisional</AlertTitle>
          <AlertDescription>
            {report.provisional_runs ?? "Some"} runs were scored against draft keys (before review): these numbers test the pipeline and are not results.
          </AlertDescription>
        </Alert>
      )}
      {report.complete === false && (
        <Alert className="border-status-warning/60">
          <HourglassIcon className="text-status-warning" />
          <AlertTitle>Judge verdicts pending</AlertTitle>
          <AlertDescription>
            {pending.length ? `${pending.length} runs have support verdicts pending (${pending.slice(0, 4).join(", ")}${pending.length > 4 ? ", …" : ""}); the primary test waits for them. ` : ""}
            Soft scores with pending decisions are left out of their means. Run `score batch` with the judge until none is pending.
          </AlertDescription>
        </Alert>
      )}
      {unverified.length > 0 && (
        <p className="text-xs text-muted-foreground">{unverified.length} scored runs were not verified (no corpus when scored).</p>
      )}
    </div>
  )
}

function ChartCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card className="min-w-0">
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
    return <EmptyState title="The primary test is not in the report" description="report.json has no `primary` section." />
  }
  const [on, off] = conditionBars(report, "support_share")
  const tests = sensitivity(report)
  return (
    <Card className="border-2">
      <CardHeader>
        <CardDescription>Pre-registered primary outcome</CardDescription>
        <CardTitle className="text-lg leading-snug">
          Share of answer facts whose quote supports them (judge), claim on vs claim off after attach
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <p className="text-xs text-muted-foreground">Mean difference (claim on − claim off)</p>
            <p className="text-4xl font-semibold tabular-nums">{pp(p.mean_difference)}</p>
            <p className="text-sm text-muted-foreground tabular-nums">
              {p.ci_low !== null && p.ci_high !== null ? `95% ${p.ci_method ?? "BCa"} interval [${pp(p.ci_low)}, ${pp(p.ci_high)}]` : `no interval (${p.ci_method ?? "too few questions"})`}
            </p>
            <p className="text-xs text-muted-foreground tabular-nums">claim on {pct(on.mean)} · claim off {pct(off.mean)}</p>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <div><dt className="text-muted-foreground">Test</dt><dd>Wilcoxon signed-rank, {p.alternative}</dd></div>
            <div><dt className="text-muted-foreground">Paired questions</dt><dd className="tabular-nums">{p.n_pairs} ({p.n_nonzero} non-zero)</dd></div>
            <div><dt className="text-muted-foreground">W · rank-biserial</dt><dd className="tabular-nums">{num(p.statistic, 1)} · {num(p.rank_biserial)}</dd></div>
            <div><dt className="text-muted-foreground">p (α = {p.alpha})</dt><dd className="tabular-nums">{pValue(p.p_value)}</dd></div>
          </dl>
          <Verdict computed={p.computed} significant={p.significant} alpha={p.alpha} />
        </div>
        {!p.computed && p.reason && <p className="text-sm text-muted-foreground">Not computed: {p.reason}.</p>}
        {p.excluded_questions.length > 0 && (
          <p className="text-xs text-muted-foreground">Left out (no value in both conditions): {p.excluded_questions.join(", ")}.</p>
        )}
        {tests.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-sm font-medium">Sensitivity analyses</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Variant</TableHead>
                  <TableHead className="text-right">Δ mean</TableHead>
                  <TableHead className="text-right">95% interval</TableHead>
                  <TableHead className="text-right">p</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tests.map((t) => (
                  <TableRow key={t.key}>
                    <TableCell className="whitespace-normal">{t.label ?? t.outcome}</TableCell>
                    <TableCell className="text-right tabular-nums">{pp(t.mean_difference)}</TableCell>
                    <TableCell className="text-right tabular-nums">{t.ci_low !== null && t.ci_high !== null ? `[${pp(t.ci_low)}, ${pp(t.ci_high)}]` : "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{t.computed ? pValue(t.p_value) : "not computed"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Verdict({ computed, significant, alpha }: { computed: boolean; significant: boolean | null; alpha: number }) {
  if (!computed || significant === null) return <StatusBadge tone="neutral" icon={<CircleSlashIcon />}>not computed</StatusBadge>
  return significant ? (
    <StatusBadge tone="good" icon={<CheckCircle2Icon />}>significant at α = {alpha}</StatusBadge>
  ) : (
    <StatusBadge tone="neutral" icon={<CircleMinusIcon />}>not significant at α = {alpha}</StatusBadge>
  )
}

function Coverage({ report }: { report: ResultsReport }) {
  const c = report.coverage
  if (!c) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Coverage</CardTitle>
        <CardDescription>Scored runs per condition and how many gave an answer with facts (only those have a support share).</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {(["claim_on", "claim_off"] as const).map((k) => (
            <div key={k} className="space-y-1">
              <dt className="text-muted-foreground">{k === "claim_on" ? "claim on" : "claim off"}</dt>
              <dd className="tabular-nums">
                {int(c[k]?.answered)} of {int(c[k]?.scored)} scored runs answered ({pct(c[k]?.answered_share, 0)})
                {c[k]?.not_scored ? ` · ${c[k]?.not_scored} planned runs not scored` : ""}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function Secondary({ report }: { report: ResultsReport }) {
  const rows = differences(report, SECONDARY)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Secondary outcomes</CardTitle>
        <CardDescription>Means by condition and the paired mean difference with its 95% interval (no tests, as pre-registered).</CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">The report has no secondary outcomes.</p>
        ) : (
          <Table>
            <caption className="sr-only">Secondary outcomes by condition</caption>
            <TableHeader>
              <TableRow>
                <TableHead>Outcome</TableHead>
                <TableHead className="text-right">claim on</TableHead>
                <TableHead className="text-right">claim off</TableHead>
                <TableHead className="text-right">Δ mean</TableHead>
                <TableHead className="text-right">95% interval</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((d) => {
                const [on, off] = conditionBars(report, d.outcome)
                const v = (x: number | null) => outcomeValue(d.kind, x)
                return (
                  <TableRow key={d.outcome}>
                    <TableCell>{d.label}</TableCell>
                    <TableCell className="text-right tabular-nums">{v(on.mean)}</TableCell>
                    <TableCell className="text-right tabular-nums">{v(off.mean)}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{outcomeDifference(d.kind, d.mean)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {d.low !== null && d.high !== null ? `[${outcomeDifference(d.kind, d.low)}, ${outcomeDifference(d.kind, d.high)}]` : "—"}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function PerQuestion({ report }: { report: ResultsReport }) {
  const questions = useQuestions()
  const category = new Map(questions.data?.map((q) => [q.id, q.category]))
  const support = questionRows(report, "support_share")
  const at = (outcome: Outcome) => new Map(questionRows(report, outcome).map((r) => [r.qid, r]))
  const [f1, unsourced, tok] = [at("fact_f1"), at("unsourced_share"), at("tokens")]
  return (
    <Card>
      <CardHeader>
        <CardTitle>Per question</CardTitle>
        <CardDescription>Means over the repeats; Δ = claim on − claim off. The values behind the charts above.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <caption className="sr-only">Outcomes per question and condition</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Question</TableHead>
              <TableHead className="text-right">Runs on / off</TableHead>
              <TableHead className="text-right">Support on</TableHead>
              <TableHead className="text-right">Support off</TableHead>
              <TableHead className="text-right">Δ support</TableHead>
              <TableHead className="text-right">Fact F1 on / off</TableHead>
              <TableHead className="text-right">Unsourced on / off</TableHead>
              <TableHead className="text-right">Tokens on / off</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {support.map((row) => (
              <TableRow key={row.qid}>
                <TableCell>
                  <span className="font-mono">{row.qid}</span>
                  {category.get(row.qid) && <Badge variant="secondary" className="ml-2 font-normal">{category.get(row.qid)!.replace("_", " ")}</Badge>}
                  {row.pending > 0 && <HourglassIcon className="ml-1 inline size-3 text-muted-foreground" aria-label={`${row.pending} runs with verdicts pending`} />}
                </TableCell>
                <TableCell className="text-right tabular-nums">{row.runs.claim_on} / {row.runs.claim_off}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(row.on)}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(row.off)}</TableCell>
                <TableCell className="text-right font-medium tabular-nums">{pp(row.diff)}</TableCell>
                <TableCell className="text-right tabular-nums">{num(f1.get(row.qid)?.on)} / {num(f1.get(row.qid)?.off)}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(unsourced.get(row.qid)?.on, 0)} / {pct(unsourced.get(row.qid)?.off, 0)}</TableCell>
                <TableCell className="text-right tabular-nums">{tokens(tok.get(row.qid)?.on)} / {tokens(tok.get(row.qid)?.off)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
