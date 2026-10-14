/**
 * Answer facts and their support status (Run page, Answer tab, and Compare).
 *
 * A fact's badge must show the verdict behind the primary outcome, so it is the label scoring
 * wrote to score.json (`detail.support`: supports / partial / no / unsourced / pending; the
 * walk's `label` is the same value). Before a run is scored a fact with no accepted claim is
 * still *unsourced* (claim_on: never claimed; claim_off: the attach step found no source), and
 * one with claims is *not judged yet*; its walk can ask the judge.
 */
import type { Answer, AnswerRow, Fact, FactLabel, Score } from "@/api/types"

export type FactStatus = "supported" | "partial" | "not_supported" | "unsourced" | "pending" | "unjudged"

const FROM_LABEL: Record<FactLabel, FactStatus> = {
  supports: "supported",
  partial: "partial",
  no: "not_supported",
  unsourced: "unsourced",
  pending: "pending",
}

/** The status of a fact from scoring's label, else from whether it cites any claim. */
export function factStatus(fact: Pick<Fact, "claims">, label: FactLabel | null | undefined): FactStatus {
  if (label && label in FROM_LABEL) return FROM_LABEL[label]
  return fact.claims.length === 0 ? "unsourced" : "unjudged"
}

export const FACT_STATUS_LABEL: Record<FactStatus, string> = {
  supported: "supported",
  partial: "partial",
  not_supported: "not supported",
  unsourced: "unsourced",
  pending: "verdict pending",
  unjudged: "not judged yet",
}

export const FACT_STATUSES = Object.keys(FACT_STATUS_LABEL) as FactStatus[]

const factKey = (rowId: string, factId: string) => `${rowId}\u0000${factId}`

/** Scoring's label per fact (row id + fact id) from score.json's detail.support. */
export function scoredLabels(score: Score | null | undefined): Map<string, FactLabel> {
  const map = new Map<string, FactLabel>()
  for (const entry of score?.detail?.support ?? []) {
    if (entry && typeof entry.fact_id === "string") map.set(factKey(entry.row_id, entry.fact_id), entry.label)
  }
  return map
}

/** Every fact's status, keyed by row and fact id (fact ids are unique per answer, rows make sure). */
export function factStatuses(answer: Answer | null | undefined, score: Score | null | undefined): Map<string, FactStatus> {
  const labels = scoredLabels(score)
  const map = new Map<string, FactStatus>()
  for (const { fact, rowId } of answerFacts(answer)) {
    map.set(factKey(rowId, fact.id), factStatus(fact, labels.get(factKey(rowId, fact.id))))
  }
  return map
}

export const statusOf = (statuses: Map<string, FactStatus>, rowId: string, fact: Fact): FactStatus =>
  statuses.get(factKey(rowId, fact.id)) ?? factStatus(fact, null)

/** A graph answer's row (an edge) rather than a table row. */
export function isGraphRow(row: AnswerRow): row is AnswerRow & { source: string; predicate: string; target: string } {
  return typeof row.source === "string" && typeof row.predicate === "string" && typeof row.target === "string"
}

export interface FactRef {
  fact: Fact
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
export function statusCounts(statuses: Iterable<FactStatus>): Record<FactStatus, number> {
  const counts = Object.fromEntries(FACT_STATUSES.map((s) => [s, 0])) as Record<FactStatus, number>
  for (const status of statuses) counts[status] += 1
  return counts
}

/** A triple's value as text (s, p, o may be any JSON value in a claim). */
export const term = (value: unknown): string =>
  value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value)
