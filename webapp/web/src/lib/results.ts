/**
 * $RUNS/report/report.json (scoring/report.py, schema_version 2) -> chart and table rows (Results
 * page; plan "Frontend pages" 6).
 *
 * This is the only module that reads the report's structure. The report keeps per outcome a mean
 * over questions for each condition with its BCa interval and the paired difference
 * (`summary`), per question x condition the means over the repeats (`per_question`, long format),
 * the paired values per question (`paired`) and the pre-registered test (`primary`). Charts get
 * one row per condition (or per outcome, both conditions as series) with the interval as
 * recharts' ErrorBar expects it: distances below and above the mean. Colour follows the condition
 * everywhere: claim_on is series 1, claim_off series 2.
 */
import type { Condition, Interval, Outcome, PairedTest, QuestionResult, ResultsReport } from "@/api/types"

import { CONDITION_LABEL } from "./format"

export const CONDITIONS: Condition[] = ["claim_on", "claim_off"]

/** scoring/report.py OUTCOMES labels, for reports that leave a label out. */
export const OUTCOME_LABEL: Record<Outcome, string> = {
  support_share: "Support share (judge)",
  fact_precision: "Fact precision (soft)",
  fact_recall: "Fact recall (soft)",
  fact_f1: "Fact F1 (soft)",
  fact_f1_normalised: "Fact F1 (normalised)",
  fact_f1_strict: "Fact F1 (strict)",
  row_f1: "Row F1 (soft)",
  row_f1_normalised: "Row F1 (normalised)",
  vital_recall: "Vital recall (soft)",
  judged_precision: "Judged precision",
  unsourced_share: "Unsourced share",
  claims_per_fact: "Claims per sourced fact",
  tokens: "Tokens",
  tokens_without_attach: "Tokens without attach",
  seconds: "Time (s, active)",
  seconds_without_attach: "Time without attach (s)",
}

export type OutcomeKind = "share" | "count" | "seconds" | "number"

export function outcomeKind(outcome: string): OutcomeKind {
  if (outcome.startsWith("tokens")) return "count"
  if (outcome.startsWith("seconds")) return "seconds"
  if (outcome === "claims_per_fact") return "number"
  return "share"
}

export const outcomeLabel = (report: ResultsReport, outcome: Outcome) => report.summary?.[outcome]?.label ?? OUTCOME_LABEL[outcome]

/** Distances below and above the mean, for <ErrorBar>; null without both bounds. */
export function errorOf(mean: number | null, low: number | null, high: number | null): [number, number] | null {
  if (mean === null || low === null || high === null) return null
  return [Math.max(0, mean - low), Math.max(0, high - mean)]
}

export interface ConditionBar {
  condition: Condition
  label: string
  mean: number | null
  low: number | null
  high: number | null
  /** [below, above] the mean, for <ErrorBar dataKey="error" />; null when there is no interval */
  error: [number, number] | null
  /** questions the mean is over */
  n: number
  method: string | null
}

const EMPTY: Interval = { n: 0, mean: null, low: null, high: null, method: null }

/** One bar per condition for one outcome, with its interval. Conditions without data are kept (mean null). */
export function conditionBars(report: ResultsReport, outcome: Outcome): ConditionBar[] {
  return CONDITIONS.map((condition) => {
    const { mean, low, high, n, method } = report.summary?.[outcome]?.[condition] ?? EMPTY
    return { condition, label: CONDITION_LABEL[condition], mean, low, high, error: errorOf(mean, low, high), n, method }
  })
}

/** One group per outcome, both conditions as series: the rows of a grouped bar chart with intervals. */
export interface MetricGroup {
  outcome: Outcome
  label: string
  claim_on: number | null
  claim_off: number | null
  claim_on_error: [number, number] | null
  claim_off_error: [number, number] | null
  claim_on_ci: [number, number] | null
  claim_off_ci: [number, number] | null
}

const ci = (b: ConditionBar): [number, number] | null => (b.low !== null && b.high !== null ? [b.low, b.high] : null)

export function metricGroups(report: ResultsReport, outcomes: Outcome[], short: Partial<Record<Outcome, string>> = {}): MetricGroup[] {
  return outcomes.map((outcome) => {
    const [on, off] = conditionBars(report, outcome)
    return {
      outcome, label: short[outcome] ?? outcomeLabel(report, outcome),
      claim_on: on.mean, claim_off: off.mean, claim_on_error: on.error, claim_off_error: off.error,
      claim_on_ci: ci(on), claim_off_ci: ci(off),
    }
  })
}

/**
 * Tokens or seconds with and without the attach step, grouped by measure so the colour stays the
 * condition's; with their intervals. claim_on has no attach step, so its two values are equal.
 */
export function costGroups(report: ResultsReport, kind: "tokens" | "seconds"): MetricGroup[] {
  const without: Outcome = kind === "tokens" ? "tokens_without_attach" : "seconds_without_attach"
  return metricGroups(report, [kind, without], { [kind]: "with attach", [without]: "without attach" })
}

/** The paired mean difference (claim_on - claim_off) of an outcome with its interval. */
export interface DifferenceRow {
  outcome: Outcome
  label: string
  kind: OutcomeKind
  mean: number | null
  low: number | null
  high: number | null
  n: number
  method: string | null
}

export function differences(report: ResultsReport, outcomes: Outcome[]): DifferenceRow[] {
  return outcomes
    .filter((o) => report.summary?.[o])
    .map((outcome) => {
      const d = report.summary?.[outcome]?.difference ?? EMPTY
      return { outcome, label: outcomeLabel(report, outcome), kind: outcomeKind(outcome), mean: d.mean, low: d.low, high: d.high, n: d.n, method: d.method }
    })
}

export interface QuestionRow {
  qid: string
  /** runs per condition that were scored */
  runs: { claim_on: number; claim_off: number }
  on: number | null
  off: number | null
  /** on minus off (the report's paired difference); null when either is missing */
  diff: number | null
  /** runs with a judge verdict still pending (their support share is not in the mean) */
  pending: number
}

const valueOf = (q: QuestionResult | undefined, outcome: Outcome): number | null => {
  const v = q?.[outcome]
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

/** Per-question values of one outcome, both conditions and their difference, in qid order. */
export function questionRows(report: ResultsReport, outcome: Outcome): QuestionRow[] {
  const byQid = new Map<string, Partial<Record<Condition, QuestionResult>>>()
  for (const q of report.per_question ?? []) {
    if (q.condition !== "claim_on" && q.condition !== "claim_off") continue
    byQid.set(q.qid, { ...byQid.get(q.qid), [q.condition]: q })
  }
  const paired = new Map((report.paired ?? []).map((p) => [p.qid, p]))
  return [...byQid.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([qid, c]) => {
      const on = valueOf(c.claim_on, outcome)
      const off = valueOf(c.claim_off, outcome)
      const reported = paired.get(qid)?.[outcome]?.difference
      return {
        qid,
        runs: { claim_on: c.claim_on?.runs ?? 0, claim_off: c.claim_off?.runs ?? 0 },
        on, off,
        diff: typeof reported === "number" ? reported : on !== null && off !== null ? on - off : null,
        pending: (c.claim_on?.pending_runs ?? 0) + (c.claim_off?.pending_runs ?? 0),
      }
    })
}

/** One point per paired question: its difference (on - off) for the difference plot. */
export function pairedDifferences(report: ResultsReport, outcome: Outcome): { qid: string; difference: number }[] {
  return questionRows(report, outcome)
    .filter((r): r is QuestionRow & { diff: number } => r.diff !== null)
    .map((r) => ({ qid: r.qid, difference: r.diff }))
}

/** Upper end of a share axis: 1, or a little above the highest interval end if that is larger. */
export function shareDomainMax(bars: { high: number | null; mean: number | null }[]): number {
  const top = Math.max(0, ...bars.map((b) => b.high ?? b.mean ?? 0))
  return top <= 1 ? 1 : Math.ceil(top * 10) / 10
}

/** The sensitivity analyses of the primary test, labelled. */
export function sensitivity(report: ResultsReport): (PairedTest & { key: string })[] {
  const p = report.primary
  if (!p) return []
  return (["sensitivity_empty_as_zero", "sensitivity_other_mapping", "sensitivity_first_claim"] as const)
    .filter((k) => p[k])
    .map((k) => ({ ...p[k]!, key: k }))
}
