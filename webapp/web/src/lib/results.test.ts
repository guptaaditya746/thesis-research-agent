import { describe, expect, it } from "vitest"

import type { ResultsReport } from "@/api/types"
import { RESULTS } from "@/mocks/fixtures"

import { conditionBars, costGroups, differences, errorOf, metricGroups, outcomeKind, pairedDifferences, questionRows, sensitivity, shareDomainMax } from "./results"

const summary = RESULTS.summary!

describe("results report to chart data", () => {
  it("gives one bar per condition with the interval as distances from the mean", () => {
    const [on, off] = conditionBars(RESULTS, "support_share")
    expect(on).toMatchObject({ condition: "claim_on", label: "claim on", mean: 0.71, low: 0.63, high: 0.78, n: 12, method: "BCa" })
    expect(on.error![0]).toBeCloseTo(0.08)
    expect(on.error![1]).toBeCloseTo(0.07)
    expect(off).toMatchObject({ condition: "claim_off", mean: 0.52 })
  })

  it("keeps a condition or an outcome without data, with no interval", () => {
    const report: ResultsReport = { ...RESULTS, summary: { support_share: { ...summary.support_share!, claim_off: { n: 0, mean: null, low: null, high: null, method: null } } } }
    expect(conditionBars(report, "support_share")[1]).toMatchObject({ mean: null, low: null, high: null, error: null, n: 0 })
    expect(conditionBars(report, "fact_f1").map((b) => b.mean)).toEqual([null, null])
    expect(conditionBars({}, "support_share")[0].error).toBeNull()
  })

  it("has no error bar without both bounds, and clips a bound on the wrong side of the mean", () => {
    expect(errorOf(0.5, null, 0.7)).toBeNull()
    expect(errorOf(0.5, 0.55, 0.7)).toEqual([0, expect.closeTo(0.2)])
    // one question: a mean and no interval (scoring/report.py interval(), n < 2)
    const report: ResultsReport = { summary: { support_share: { ...summary.support_share!, claim_on: { n: 1, mean: 0.4, low: null, high: null, method: "none (fewer than 2 questions)" } } } }
    expect(conditionBars(report, "support_share")[0]).toMatchObject({ mean: 0.4, error: null })
  })

  it("groups several outcomes with both conditions as series, labelled from the report", () => {
    const groups = metricGroups(RESULTS, ["fact_f1", "row_f1"])
    expect(groups.map((g) => g.label)).toEqual(["Fact F1 (soft)", "Row F1 (soft)"])
    expect(groups[0]).toMatchObject({ claim_on: 0.54, claim_off: 0.53, claim_on_ci: [0.46, 0.62], claim_off_ci: [0.45, 0.61] })
    expect(groups[1].claim_off_error?.[0]).toBeCloseTo(0.08)
    expect(metricGroups(RESULTS, ["fact_f1"], { fact_f1: "fact F1" })[0].label).toBe("fact F1")
  })

  it("shows cost with and without attach, colour kept per condition", () => {
    const [withAttach, without] = costGroups(RESULTS, "tokens")
    expect(withAttach).toMatchObject({ label: "with attach", claim_on: 1_284_000, claim_off: 1_398_000 })
    expect(without).toMatchObject({ label: "without attach", claim_on: 1_284_000, claim_off: 1_102_000, claim_off_ci: [948_000, 1_260_000] })
    expect(costGroups(RESULTS, "seconds")[1].claim_off).toBe(2_890)
  })

  it("reads the paired differences with their intervals and units", () => {
    const rows = differences(RESULTS, ["unsourced_share", "tokens", "judged_precision"])
    expect(rows.map((r) => r.outcome)).toEqual(["unsourced_share", "tokens"]) // judged_precision is not in this report
    expect(rows[0]).toMatchObject({ kind: "share", mean: -0.15, low: -0.17, high: -0.13, n: 12 })
    expect(rows[1].kind).toBe("count")
    expect([outcomeKind("seconds_without_attach"), outcomeKind("claims_per_fact"), outcomeKind("fact_f1")]).toEqual(["seconds", "number", "share"])
  })

  it("lists the questions in order with on, off and the report's paired difference", () => {
    const rows = questionRows(RESULTS, "support_share")
    expect(rows.map((r) => r.qid)).toEqual(["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10", "q11", "q12"])
    expect(rows[0]).toMatchObject({ runs: { claim_on: 3, claim_off: 3 }, on: 0.74, off: 0.55, pending: 0 })
    expect(rows[0].diff).toBeCloseTo(0.19)
    // without a paired record the difference is computed; a missing side leaves it null
    const onlyOn = { ...RESULTS, paired: [], per_question: RESULTS.per_question!.filter((q) => q.qid !== "q01" || q.condition === "claim_on") }
    const q01 = questionRows(onlyOn, "support_share")[0]
    expect(q01).toMatchObject({ qid: "q01", on: 0.74, off: null, diff: null, runs: { claim_on: 3, claim_off: 0 } })
    expect(questionRows(onlyOn, "support_share")[1].diff).toBeCloseTo(0.2)
  })

  it("gives the per-question differences of the paired questions", () => {
    const diffs = pairedDifferences(RESULTS, "support_share")
    expect(diffs).toHaveLength(12)
    expect(diffs[0].qid).toBe("q01")
    expect(diffs[0].difference).toBeCloseTo(0.19)
  })

  it("lists the primary test's sensitivity analyses", () => {
    expect(sensitivity(RESULTS).map((t) => t.key)).toEqual(["sensitivity_empty_as_zero", "sensitivity_other_mapping", "sensitivity_first_claim"])
    expect(sensitivity({ ...RESULTS, primary: null })).toEqual([])
  })

  it("extends a share axis only when an interval goes past 1", () => {
    expect(shareDomainMax(conditionBars(RESULTS, "support_share"))).toBe(1)
    expect(shareDomainMax([{ mean: 1, high: 1.12 }])).toBe(1.2)
  })
})
