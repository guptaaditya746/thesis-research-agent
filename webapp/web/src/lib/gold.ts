/**
 * A question's gold state (GET /api/gold) as the Gold page shows it. The backend passes the gold
 * files through as they are: doc.json's `coverage` and `counts` (gold/build.py) and the review's
 * report.json (gold/agreement.py); any may be missing while the gold standard is being built or
 * reviewed, so each view is null when its file is.
 */
import type { GoldCounts, GoldCoverage, GoldEntry, GoldReport } from "@/api/types"

const obj = <T>(v: unknown): T | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as T) : null)
const n = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null)

export interface GoldView {
  coverage: GoldCoverage | null
  counts: GoldCounts | null
  report: GoldReport | null
  /** records decided of all review records (Argilla), when the review has a report */
  review: { decided: number; records: number; kept: number | null; disagreements: number } | null
  /**
   * Cohen's kappa of the `keep` decision on the overlap, with its bootstrap 95 % interval, the bar
   * it should meet, and whether the overlap records are all from the independent round (if not,
   * gold/agreement.py's `warning` says why the value is no agreement result)
   */
  kappa: {
    value: number | null
    low: number | null
    high: number | null
    items: number | null
    bar: number | null
    meetsBar: boolean | null
    independent: boolean | null
    warning: string | null
  } | null
  /** facts triage left outside the reviewed tiers (estimate, 95 % Wilson bounds) */
  triageMissed: { estimate: number | null; low: number | null; high: number | null } | null
  /** share of sampled not-relevant papers someone found relevant (95 % Wilson bounds) */
  screeningFalseNegative: { rate: number | null; low: number | null; high: number | null; checked: number | null } | null
}

export function goldView(entry: GoldEntry): GoldView {
  const report = obj<GoldReport>(entry.report)
  const review = obj<NonNullable<GoldReport["review"]>>(report?.review)
  const kappa = obj<NonNullable<GoldReport["kappa"]>>(report?.kappa)
  const triage = obj<NonNullable<GoldReport["triage"]>>(report?.triage)
  const screening = obj<NonNullable<GoldReport["screening"]>>(report?.screening)
  return {
    coverage: obj<GoldCoverage>(entry.coverage),
    counts: obj<GoldCounts>(entry.counts),
    report,
    review: review
      ? { decided: n(review.decided) ?? 0, records: n(review.records) ?? 0, kept: n(review.kept), disagreements: n(review.disagreements) ?? 0 }
      : null,
    kappa: kappa
      ? {
          value: n(kappa.keep?.kappa), low: n(kappa.keep?.kappa_95?.[0]), high: n(kappa.keep?.kappa_95?.[1]),
          items: n(kappa.keep?.items) ?? n(kappa.items), bar: n(kappa.bar),
          meetsBar: typeof kappa.keep_kappa_meets_bar === "boolean" ? kappa.keep_kappa_meets_bar : null,
          independent: typeof kappa.independent === "boolean" ? kappa.independent : null,
          warning: typeof kappa.warning === "string" && kappa.warning ? kappa.warning : null,
        }
      : null,
    triageMissed: triage
      ? { estimate: n(triage.estimated_missed), low: n(triage.estimated_missed_95?.[0]), high: n(triage.estimated_missed_95?.[1]) }
      : null,
    screeningFalseNegative: screening
      ? {
          rate: n(screening.false_negative_rate), low: n(screening.false_negative_rate_95?.[0]),
          high: n(screening.false_negative_rate_95?.[1]), checked: n(screening.checked),
        }
      : null,
  }
}

/**
 * The gold build stopped short of a draft key: `building` with the builder's stage done (D is
 * there, triage, pool or draft did not run) or failed. With no gold job active, it can be run again
 * (POST /api/gold/{qid}/build reruns build, triage, pool and draft).
 */
export const buildStopped = (entry: Pick<GoldEntry, "status" | "stage">): boolean =>
  entry.status === "building" && (entry.stage === "done" || entry.stage === "failed")

/** The builder's stage in words, for a question whose gold is being built. */
export function stageText(entry: Pick<GoldEntry, "status" | "stage">): string | null {
  if (!entry.stage) return null
  if (entry.status === "building" && (entry.stage === "done" || entry.stage === "failed")) {
    return entry.stage === "done" ? "D built; triage, pool and draft key still to run" : "the build stopped; run it again"
  }
  return entry.stage
}
