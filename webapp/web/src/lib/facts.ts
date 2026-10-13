/**
 * Answer facts and their support status (Run page, Answer tab and Compare).
 *
 * A fact with no claim is *unsourced* (claim_on: never claimed; claim_off: the attach step
 * found no source). A fact with claims gets the judge's verdict from its claim walk
 * (gold/judge.py: supports / partial / no); before the judge has run it is *sourced* only.
 */
import type { Answer, AnswerFact, AnswerRow, GraphRow, Verdict } from "@/api/types"

export type FactStatus = "supported" | "partial" | "not_supported" | "unsourced" | "unjudged"

export function factStatus(fact: Pick<AnswerFact, "claims">, verdict: Verdict | null | undefined): FactStatus {
  if (fact.claims.length === 0) return "unsourced"
  if (!verdict) return "unjudged"
  return verdict.label === "supports" ? "supported" : verdict.label === "partial" ? "partial" : "not_supported"
}

export const FACT_STATUS_LABEL: Record<FactStatus, string> = {
  supported: "supported",
  partial: "partial",
  not_supported: "not supported",
  unsourced: "unsourced",
  unjudged: "sourced, not judged",
}

export function isGraphRow(row: AnswerRow): row is GraphRow {
  return "source" in row && "predicate" in row
}

export interface FactRef {
  fact: AnswerFact
  rowId: string
}

/** Every fact of an answer with its row, in answer order. */
export function answerFacts(answer: Answer | null | undefined): FactRef[] {
  return (answer?.rows ?? []).flatMap((row) => row.facts.map((fact) => ({ fact, rowId: row.id })))
}

/** claim id -> the facts that cite it (a claim may back several facts). */
export function factsByClaim(answer: Answer | null | undefined): Map<string, FactRef[]> {
  const map = new Map<string, FactRef[]>()
  for (const ref of answerFacts(answer)) {
    for (const claim of ref.fact.claims) map.set(claim, [...(map.get(claim) ?? []), ref])
  }
  return map
}

/** Counts per status, for the answer's legend line. */
export function statusCounts(statuses: FactStatus[]): Record<FactStatus, number> {
  const counts: Record<FactStatus, number> = { supported: 0, partial: 0, not_supported: 0, unsourced: 0, unjudged: 0 }
  for (const status of statuses) counts[status] += 1
  return counts
}
