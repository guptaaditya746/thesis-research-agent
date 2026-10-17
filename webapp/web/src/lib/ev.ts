/**
 * Reading the evidence-level files for display (pure functions, unit-tested in ev.test.ts): systems and
 * their series colours, directions, evidence types, extractor ids, intervals, the funnel's decisions, the
 * scores of report.json arranged per level and system, and item labels.
 *
 * Colours: one series colour per system (the engine and the two baselines), the same on every chart and
 * badge; evidence types get their own marks in the paper text. Colour never carries meaning alone: every
 * mark has a label next to it or in its title.
 */
import type { Direction, EvRunSummary, FunnelDoc, Interval, Item, Report, SynthesisScore } from "@/api/ev"
import { cell, DASH, num } from "@/lib/format"

export const ENGINE = "evidence-engine"

export const SYSTEM_LABEL: Record<string, string> = {
  "evidence-engine": "evidence engine",
  "rag-baseline": "RAG baseline",
  "agent-baseline": "agent baseline",
}
export const SYSTEM_COLOR: Record<string, string> = {
  "evidence-engine": "var(--chart-1)",
  "rag-baseline": "var(--chart-2)",
  "agent-baseline": "var(--chart-3)",
}
export const systemLabel = (system: string | null | undefined) => (system ? (SYSTEM_LABEL[system] ?? system) : DASH)
export const systemColor = (system: string) => SYSTEM_COLOR[system] ?? "var(--muted-foreground)"
/** The engine first, then the baselines in a fixed order, then anything else by name. */
export function systemOrder(a: string, b: string): number {
  const order = Object.keys(SYSTEM_LABEL)
  const ia = order.indexOf(a)
  const ib = order.indexOf(b)
  return (ia < 0 ? order.length : ia) - (ib < 0 ? order.length : ib) || a.localeCompare(b)
}

export const EVIDENCE_TYPES = ["condition", "metric", "measurement", "author_claim"] as const
export const TYPE_LABEL: Record<string, string> = {
  condition: "condition",
  metric: "metric",
  measurement: "measurement",
  author_claim: "author claim",
  screen: "screen",
  document: "paper",
}
/** The mark colour of an evidence type in the paper text and the graph. */
export const TYPE_COLOR: Record<string, string> = {
  condition: "var(--chart-1)",
  metric: "var(--chart-4)",
  measurement: "var(--chart-3)",
  author_claim: "var(--chart-5)",
  screen: "var(--muted-foreground)",
}
export const typeLabel = (type: string) => TYPE_LABEL[type] ?? type

export const DIRECTION_LABEL: Record<Direction, string> = {
  supports: "supports",
  contradicts: "contradicts",
  neutral: "neutral",
  undetermined: "undetermined",
}
/** Status tone of a direction: supporting and contradicting are both findings, so neither is "good". */
export const DIRECTION_TONE: Record<Direction, "good" | "critical" | "neutral" | "warning"> = {
  supports: "good",
  contradicts: "critical",
  neutral: "neutral",
  undetermined: "warning",
}

/** A table cell: shares and rates with three decimals, counts whole, booleans in words, lists joined. */
export function evCell(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === "boolean") return value ? "yes" : "no"
  return cell(value)
}

/** `name@version#hash` -> its parts; an id without them is all name. */
export function splitExtractor(id: string): { name: string; version: string | null; hash: string | null } {
  const [name, rest] = id.split("@", 2)
  if (rest === undefined) return { name: id, version: null, hash: null }
  const [version, hash] = rest.split("#", 2)
  return { name, version: version || null, hash: hash ?? null }
}
export const extractorName = (id: string) => splitExtractor(id).name

/** `group~name` of a run or a score directory, as its two parts. */
export function splitRef(id: string): { group: string; name: string | null } {
  const at = id.indexOf("~")
  return at < 0 ? { group: id, name: null } : { group: id.slice(0, at), name: id.slice(at + 1) }
}

/** `0.812 [0.74, 0.88]` (the report's own form), the point alone when the interval is degenerate. */
export function intervalText(row: Interval | null | undefined, digits = 3): string {
  if (!row || row.point === null || row.point === undefined) return DASH
  const point = num(row.point, digits)
  if (row.low === null || row.low === undefined || row.high === null || row.high === undefined) return `${point} [n/a]`
  return `${point} [${num(row.low, 2)}, ${num(row.high, 2)}]`
}

/** Words for where the funnel stopped on a document (Part D). */
export function funnelStop(doc: FunnelDoc | null | undefined, strategy?: string | null): string {
  if (!doc) return DASH
  if (doc.skipped) return "skipped (screened out)"
  if (doc.stopped_after !== null && doc.stopped_after !== undefined) return `complete after position ${doc.stopped_after}`
  if (strategy === "all") return "every extractor ran (all)"
  const last = doc.decisions?.at(-1)
  return last?.gap ? `exhausted, gap ${last.gap}` : "exhausted"
}

/** A short label of an item from its fields (graph nodes, item lists). */
export function itemLabel(item: Pick<Item, "evidence_type" | "fields">): string {
  const f = item.fields as Record<string, unknown>
  switch (item.evidence_type) {
    case "condition":
      return `${String(f.label ?? "?")} (${String(f.role ?? "?")})`
    case "metric":
      return `${String(f.name ?? "?")} (${String(f.canonical ?? "?")})`
    case "measurement":
      return `${typeof f.value === "number" ? f.value : String(f.value ?? "?")}${f.dataset ? ` on ${String(f.dataset)}` : ""}`
    case "author_claim":
      return `claims: ${String(f.direction ?? "?")}`
    case "screen":
      return f.relevant ? "relevant" : "not relevant"
    default:
      return JSON.stringify(f)
  }
}

// --- scores ------------------------------------------------------------------------------------------

export const LEVELS = ["explicit", "paraphrased", "distributed", "complex", "contradictory", "mixed", "all"]
export const levelOrder = (a: string, b: string) => {
  const ia = LEVELS.indexOf(a)
  const ib = LEVELS.indexOf(b)
  return (ia < 0 ? LEVELS.length : ia) - (ib < 0 ? LEVELS.length : ib) || a.localeCompare(b)
}

type Row = Record<string, unknown>
const n = (v: unknown): number | null => (typeof v === "number" && !Number.isNaN(v) ? v : null)

/** C per level: one row per level with every system's value of `measure` (direction_accuracy, completeness, ...). */
export function synthesisByLevel(synthesis: SynthesisScore[] | undefined, measure: string): Row[] {
  const levels = new Map<string, Row>()
  for (const s of synthesis ?? []) {
    for (const r of (s.rows ?? []) as Row[]) {
      const level = String(r.level)
      const row = levels.get(level) ?? { level }
      row[s.system] = n(r[measure])
      levels.set(level, row)
    }
  }
  return [...levels.values()].sort((a, b) => levelOrder(String(a.level), String(b.level)))
}

/** A extraction rows of one level ("all" by default), one per evidence type, the overall row last. */
export function extractionRows(report: Report, level = "all"): Row[] {
  const rows = ((report.extraction?.rows as Row[] | undefined) ?? []).filter((r) => r.level === level)
  return rows.sort((a, b) => (a.evidence_type === "all" ? 1 : b.evidence_type === "all" ? -1 : String(a.evidence_type).localeCompare(String(b.evidence_type))))
}

/** Extraction F1 per level and evidence type (a row per level, a column per type). */
export function extractionByLevel(report: Report, measure = "f1"): Row[] {
  const levels = new Map<string, Row>()
  for (const r of (report.extraction?.rows as Row[] | undefined) ?? []) {
    const level = String(r.level)
    const row = levels.get(level) ?? { level }
    row[String(r.evidence_type)] = n(r[measure])
    levels.set(level, row)
  }
  return [...levels.values()].sort((a, b) => levelOrder(String(a.level), String(b.level)))
}

/** The interval rows of report.json for one section, keyed by system or evidence type. */
export function intervalsOf(report: Report, section: "extraction" | "synthesis" | "paired"): (Interval & { key: string })[] {
  const rows = ((report.intervals as Record<string, Row[] | undefined> | null | undefined)?.[section] ?? []) as Row[]
  return rows.map((r) => ({ ...(r as Interval), key: String(r.system ?? r.evidence_type ?? "") }))
}

/** One overall line per system for the C table: label, expected, correct, and the "all" row's measures. */
export function synthesisSummary(report: Report): Row[] {
  return [...(report.synthesis ?? [])]
    .sort((a, b) => systemOrder(a.system, b.system))
    .map((s) => {
      const all = ((s.rows ?? []) as Row[]).find((r) => r.level === "all") ?? {}
      return { system: s.system, label: s.label, expected: s.expected_label, label_correct: s.label_correct, ...all }
    })
}

/** A compare.json row's series: its system, and the engine's strategy when the table holds both (all vs gaps). */
export function seriesOf(row: Row, strategies: boolean): string {
  return strategies && row.strategy ? `${String(row.system)}:${String(row.strategy)}` : String(row.system)
}

const KNOBS =["duplicates", "missing", "outliers", "irrelevant"]

/** corpus.json `settings` knobs that are set (F2), in words: "duplicates 2, irrelevant 1", or "none". */
export function knobText(settings: Record<string, unknown> | null | undefined): string {
  const set = KNOBS.filter((k) => Number(settings?.[k] ?? 0) > 0).map((k) => `${k} ${String(settings?.[k])}`)
  return set.length ? set.join(", ") : "none"
}

/** Engine runs grouped by their score directory and corpus, for the "all vs gaps" view. */
export function runsByCorpus(runs: EvRunSummary[]): Map<string, EvRunSummary[]> {
  const out = new Map<string, EvRunSummary[]>()
  for (const r of runs) {
    const key = r.corpus ?? r.corpus_id ?? r.name
    out.set(key, [...(out.get(key) ?? []), r])
  }
  return out
}
