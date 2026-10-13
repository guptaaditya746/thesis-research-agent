/**
 * $RUNS/report/report.json -> chart and table rows (Results page; plan "Frontend pages" 6).
 *
 * This is the only module that reads the report's structure, so when the scoring package (WP D)
 * settles its field names only these functions change. Charts get one row per condition with
 * the mean and the interval as recharts' ErrorBar expects it (distances below and above the
 * mean); the per-question table gets the two conditions and their difference (on minus off).
 * Colour follows the condition everywhere: claim_on is series 1, claim_off series 2.
 */
import type { Condition, MetricName, QuestionResult, ResultsReport } from "@/api/types"

import { CONDITION_LABEL } from "./format"

export const CONDITIONS: Condition[] = ["claim_on", "claim_off"]

export const METRIC_LABEL: Record<MetricName, string> = {
  support_share: "Support share",
  fact_precision: "Fact precision",
  fact_recall: "Fact recall",
  fact_f1: "Fact F1",
  row_f1: "Row F1",
  vital_recall: "Vital recall",
  unsourced_share: "Unsourced share",
  tokens: "Tokens",
  tokens_without_attach: "Tokens without attach",
  seconds: "Time (s)",
  seconds_without_attach: "Time without attach (s)",
}

export interface ConditionBar {
  condition: Condition
  label: string
  mean: number | null
  low: number | null
  high: number | null
  /** [below, above] the mean, for <ErrorBar dataKey="error" />; null when there is no interval */
  error: [number, number] | null
  n: number
}

/** One bar per condition for one metric, with its interval. Conditions without data are kept (mean null). */
export function conditionBars(report: ResultsReport, metric: MetricName): ConditionBar[] {
  return CONDITIONS.map((condition) => {
    const stat = report.conditions[condition]?.[metric]
    const mean = stat?.mean ?? null
    const ci = stat?.ci ?? null
    const error: [number, number] | null =
      mean !== null && ci ? [Math.max(0, mean - ci.low), Math.max(0, ci.high - mean)] : null
    return { condition, label: CONDITION_LABEL[condition], mean, low: ci?.low ?? null, high: ci?.high ?? null, error, n: stat?.n ?? 0 }
  })
}

/** One group per metric, both conditions as series: the rows of a grouped bar chart with intervals. */
export interface MetricGroup {
  metric: MetricName
  label: string
  claim_on: number | null
  claim_off: number | null
  claim_on_error: [number, number] | null
  claim_off_error: [number, number] | null
  claim_on_ci: [number, number] | null
  claim_off_ci: [number, number] | null
}

export function metricGroups(report: ResultsReport, metrics: MetricName[]): MetricGroup[] {
  return metrics.map((metric) => {
    const [on, off] = conditionBars(report, metric)
    const ci = (b: ConditionBar): [number, number] | null => (b.low !== null && b.high !== null ? [b.low, b.high] : null)
    return {
      metric, label: METRIC_LABEL[metric],
      claim_on: on.mean, claim_off: off.mean, claim_on_error: on.error, claim_off_error: off.error,
      claim_on_ci: ci(on), claim_off_ci: ci(off),
    }
  })
}

export interface CostGroup {
  /** "with attach" or "without attach" */
  measure: string
  claim_on: number | null
  claim_off: number | null
}

/**
 * Tokens or seconds with and without the attach step, grouped by measure so the colour stays
 * the condition's. claim_on has no attach step, so its two values are equal by construction.
 */
export function costGroups(report: ResultsReport, kind: "tokens" | "seconds"): CostGroup[] {
  const value = (c: Condition, m: MetricName) => report.conditions[c]?.[m]?.mean ?? null
  const without: MetricName = kind === "tokens" ? "tokens_without_attach" : "seconds_without_attach"
  return [
    { measure: "with attach", claim_on: value("claim_on", kind), claim_off: value("claim_off", kind) },
    {
      measure: "without attach",
      claim_on: value("claim_on", without) ?? value("claim_on", kind),
      claim_off: value("claim_off", without),
    },
  ]
}

export interface QuestionRow {
  qid: string
  category: QuestionResult["category"]
  runs: string
  on: number | null
  off: number | null
  /** on minus off; null when either is missing */
  diff: number | null
}

/** Per-question values of one metric, both conditions and their difference, in qid order. */
export function questionRows(report: ResultsReport, metric: MetricName): QuestionRow[] {
  return [...report.per_question]
    .sort((a, b) => a.qid.localeCompare(b.qid))
    .map((q) => {
      const on = q.claim_on[metric] ?? null
      const off = q.claim_off[metric] ?? null
      return {
        qid: q.qid, category: q.category, runs: `${q.runs.claim_on ?? 0} / ${q.runs.claim_off ?? 0}`,
        on, off, diff: on !== null && off !== null ? on - off : null,
      }
    })
}

/** Upper end of a share axis: 1, or a little above the highest interval end if that is larger. */
export function shareDomainMax(bars: ConditionBar[]): number {
  const top = Math.max(0, ...bars.map((b) => b.high ?? b.mean ?? 0))
  return top <= 1 ? 1 : Math.ceil(top * 10) / 10
}
