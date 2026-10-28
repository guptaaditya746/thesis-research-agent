/**
 * The evidence table's rows (pure functions, unit-tested in evidence.test.ts): one row per paper of a run,
 * built from answer.json, the run's graph.json (every item with its fields, links and the extractors that
 * found it) and the run protocol's synthesis rules, so every row can say what was compared, which rule gave
 * its verdict, which extractors found the values, and which spans of the paper to highlight.
 *
 * The table follows SciDaSynth's "evidence table + source panel" (Wang et al., Campbell Systematic Reviews
 * 2025): the answer first, one row per paper grouped into lanes by verdict, one click to the sentence.
 */
import type { BestAnswer, ConsistencyAnswer, EffectAnswer, EvGraph, EvGraphNode, InventoryAnswer, Item, Study, Synthesis } from "@/api/ev"
import { DASH, num } from "@/lib/format"

import { ENGINE, extractorName, itemLabel } from "./ev"

// --- the graph, indexed -----------------------------------------------------------------------------

export interface GraphIndex {
  node: (id: string | null | undefined) => EvGraphNode | undefined
  /** the items of a paper, in graph order */
  inDocument: (doc: string) => EvGraphNode[]
  /** extractor ids that found any of these items, each once */
  foundBy: (ids: (string | null | undefined)[]) => string[]
}

const linksOf = (n: EvGraphNode | undefined) => ((n?.links ?? {}) as Record<string, string>)
export const fieldOf = (n: EvGraphNode | undefined, key: string): unknown => (n?.fields ?? {})[key]

export function indexGraph(graph: EvGraph | null | undefined): GraphIndex {
  const byId = new Map<string, EvGraphNode>()
  const byDoc = new Map<string, EvGraphNode[]>()
  for (const n of graph?.nodes ?? []) {
    byId.set(n.id, n)
    if (n.type !== "document" && n.document) byDoc.set(n.document, [...(byDoc.get(n.document) ?? []), n])
  }
  return {
    node: (id) => (id ? byId.get(id) : undefined),
    inDocument: (doc) => byDoc.get(doc) ?? [],
    foundBy: (ids) => [...new Set(ids.flatMap((id) => (id ? byId.get(id)?.found_by ?? [] : [])))],
  }
}

/** The extractor family shown in a narrow column: `regex_condition@2#…` -> "regex". */
export const extractorFamily = (id: string) => extractorName(id).split("_")[0]

// --- lanes ------------------------------------------------------------------------------------------

export type Tone = "good" | "critical" | "neutral" | "warning"
export interface Lane {
  key: string
  label: string
  tone: Tone
  /** what a row in this lane means, in plain words */
  hint: string
  /** a second look: the lane is drawn hatched in the coverage bar (duplicates, papers left out) */
  muted?: boolean
}

export const EFFECT_LANES: Lane[] = [
  { key: "supports", label: "supports", tone: "good", hint: "the treatment beats the control by at least the margin" },
  { key: "contradicts", label: "contradicts", tone: "critical", hint: "the control beats the treatment by at least the margin" },
  { key: "neutral", label: "no effect", tone: "neutral", hint: "the difference is smaller than the margin" },
  { key: "undetermined", label: "undetermined", tone: "warning", hint: "no treatment and control value to compare" },
  { key: "duplicate", label: "duplicate", tone: "neutral", hint: "repeats an earlier paper's numbers; not counted", muted: true },
  { key: "absent", label: "not in the answer", tone: "neutral", hint: "the system did not use this paper", muted: true },
]

// --- rows -------------------------------------------------------------------------------------------

/** One link of the "why" chain the source panel shows: sentence -> items -> values -> rule -> verdict. */
export interface WhyStep {
  role: string
  text: string
  /** the item whose span this step points at (a click scrolls the paper there) */
  item?: string | null
  foundBy?: string[]
}

/** What the source panel opens: a paper, the items to highlight in it, the one to scroll to, and why. */
export interface SourceTarget {
  key: string
  document: string
  title: string
  lane: string
  items: string[]
  focus: string | null
  why: WhyStep[]
  /** also mark the passages a baseline cited (`cited:` marks) */
  cited?: boolean
}

export interface EvidenceRow<T = unknown> {
  key: string
  document: string | null
  lane: string
  /** the panel target of the row as a whole (a click on the paper) */
  target: SourceTarget | null
  data: T
}

export interface Side {
  label: string | null
  value: number | null
  condition: string | null
  measurement: string | null
}

export interface EffectData {
  study: Study | null
  treatment: Side | null
  control: Side | null
  metric: { name: string; item: string | null; higherIsBetter: boolean | null } | null
  dataset: string | null
  delta: number | null
  direction: string
  /** the rule in full (the source panel) */
  rule: string
  /** the rule in a few words (the table: the metric column already says which way is better) */
  ruleShort: string
  claim: { direction: string; agrees: boolean | null; item: string | null } | null
  foundBy: string[]
}

const isNum = (v: unknown): v is number => typeof v === "number" && !Number.isNaN(v)
export const signed = (v: number | null | undefined, digits = 3) => (isNum(v) ? `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(digits)}` : DASH)

function side(pair: Study["treatment"], g: GraphIndex): Side | null {
  if (!pair) return null
  const cond = g.node(pair.condition)
  return { label: (fieldOf(cond, "label") as string | undefined) ?? null, value: pair.value ?? null, condition: pair.condition ?? null, measurement: pair.measurement ?? null }
}

/**
 * The rule that turned a study's numbers into its verdict, in words (evidence/rules.py `effect`): which way the
 * metric is better, the signed difference, and the margin (`min_effect`) it is compared with.
 */
export function effectRule(study: Study | null, synthesis: Synthesis | null | undefined, system: string): string {
  if (!study) return system === ENGINE ? "not in the answer" : "not cited by the baseline"
  if (system !== ENGINE) return study.direction === "undetermined" ? "the baseline gave no direction" : "the baseline's reading of the cited passages"
  if (study.duplicate_of && !isNum(study.delta)) return `duplicate of ${study.duplicate_of}`
  if (!isNum(study.delta)) return study.reason?.text ?? study.reason?.code ?? "no pair of values"
  const metric = synthesis?.metrics.find((m) => m.canonical === study.metric)
  const better = metric ? (metric.higher_is_better ? "higher is better" : "lower is better") : null
  const formula = metric ? (metric.higher_is_better ? "treatment − control" : "control − treatment") : "difference"
  const margin = synthesis?.min_effect
  const verdict = study.direction === "neutral" ? "no effect" : study.direction
  const compare = isNum(margin) ? `; |Δ| ${Math.abs(study.delta) >= margin ? "≥" : "<"} margin ${margin}` : ""
  return `${better ? `${study.metric}: ${better}; ` : ""}Δ = ${formula} = ${signed(study.delta)}${compare} → ${verdict}${study.duplicate_of ? ` (duplicate of ${study.duplicate_of}, not counted)` : ""}`
}

/** The rule in a few words: the size of the difference against the margin, or why there is none. */
export function effectRuleShort(study: Study | null, synthesis: Synthesis | null | undefined, system: string): string {
  if (!study || system !== ENGINE || !isNum(study.delta)) return effectRule(study, synthesis, system)
  const margin = synthesis?.min_effect
  const size = Math.abs(study.delta).toFixed(3)
  const base = isNum(margin) ? `|Δ| ${size} ${Math.abs(study.delta) >= margin ? "≥" : "<"} margin ${margin}` : `|Δ| ${size}`
  return study.duplicate_of ? `${base}; duplicate of ${study.duplicate_of}, not counted` : base
}

function effectLane(study: Study | null): string {
  if (!study) return "absent"
  if (study.duplicate_of) return "duplicate"
  return ["supports", "contradicts", "neutral"].includes(study.direction) ? study.direction : "undetermined"
}

/** One row per paper of the run (`documents`): its study, or "not in the answer" when it has none. */
export function effectRows(answer: EffectAnswer, documents: string[], graph: GraphIndex, synthesis?: Synthesis | null): EvidenceRow<EffectData>[] {
  const studies = new Map(answer.studies.map((s) => [s.document, s]))
  const docs = [...documents, ...answer.studies.map((s) => s.document).filter((d) => !documents.includes(d))]
  return docs.map((doc) => {
    const study = studies.get(doc) ?? null
    const treatment = side(study?.treatment ?? null, graph)
    const control = side(study?.control ?? null, graph)
    const tm = graph.node(treatment?.measurement)
    const metricItem = linksOf(tm).metric ?? null
    const metricNode = graph.node(metricItem)
    const metric = study?.metric
      ? {
          name: (fieldOf(metricNode, "name") as string | undefined) ?? study.metric,
          item: metricItem,
          higherIsBetter: synthesis?.metrics.find((m) => m.canonical === study.metric)?.higher_is_better ?? null,
        }
      : null
    const claimRaw = study?.author_claim as { direction?: string; agrees_with_data?: boolean | null; item?: string } | null | undefined
    const claim = claimRaw ? { direction: String(claimRaw.direction ?? DASH), agrees: claimRaw.agrees_with_data ?? null, item: claimRaw.item ?? null } : null
    const dataset = (fieldOf(tm, "dataset") as string | null | undefined) ?? null
    const items = [treatment?.measurement, treatment?.condition, control?.measurement, control?.condition, metricItem, claim?.item]
      .filter((x): x is string => !!x)
    const lane = effectLane(study)
    const rule = effectRule(study, synthesis, answer.system)
    const foundBy = graph.foundBy(items)
    const direction = study?.direction ?? "undetermined"
    const why: WhyStep[] = []
    if (treatment) why.push({ role: "treatment", text: `${treatment.label ?? "treatment"} = ${num(treatment.value, 3)}`, item: treatment.measurement, foundBy: graph.foundBy([treatment.measurement, treatment.condition]) })
    if (control) why.push({ role: "control", text: `${control.label ?? "control"} = ${num(control.value, 3)}`, item: control.measurement, foundBy: graph.foundBy([control.measurement, control.condition]) })
    if (metric) why.push({ role: "metric", text: metric.name === study?.metric ? metric.name : `${metric.name} (${study?.metric})`, item: metric.item, foundBy: graph.foundBy([metric.item]) })
    why.push({ role: "rule", text: rule })
    if (claim) why.push({ role: "author claim", text: `${claim.direction}${claim.agrees === false ? " (disagrees with the numbers)" : claim.agrees ? " (agrees with the numbers)" : ""}`, item: claim.item, foundBy: graph.foundBy([claim.item]) })
    return {
      key: doc,
      document: doc,
      lane,
      target: { key: doc, document: doc, title: doc, lane, items, focus: treatment?.measurement ?? claim?.item ?? null, why, cited: answer.system !== ENGINE },
      data: { study, treatment, control, metric, dataset, delta: study?.delta ?? null, direction, rule, ruleShort: effectRuleShort(study, synthesis, answer.system), claim, foundBy },
    }
  })
}

/** A row's target, scrolled to one of its items (a click on a cell). */
export const focusOn = (row: EvidenceRow, item: string | null | undefined): SourceTarget | null =>
  row.target ? { ...row.target, focus: item ?? row.target.focus } : null

/** Rows per lane, in lane order; lanes without rows are left out. */
export function byLane<R extends { lane: string }>(rows: R[], lanes: Lane[]): { lane: Lane; rows: R[] }[] {
  return lanes.map((lane) => ({ lane, rows: rows.filter((r) => r.lane === lane.key) })).filter((g) => g.rows.length > 0)
}

/** Count per lane, every lane listed (the coverage bar keeps its legend stable). */
export function laneCounts(rows: { lane: string }[], lanes: Lane[]): { lane: Lane; count: number }[] {
  return lanes.map((lane) => ({ lane, count: rows.filter((r) => r.lane === lane.key).length }))
}

// --- the other question kinds ---------------------------------------------------------------------

const fold = (s: unknown) => String(s ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()

/** A graph item as one line ("RAG (rag)", "0.71 on TriviaQA"), as the paper view lists items. */
export function nodeText(n: EvGraphNode | undefined): string {
  if (!n) return DASH
  return itemLabel({ evidence_type: n.type as Item["evidence_type"], fields: (n.fields ?? {}) as Record<string, unknown> })
}

/** The paper's measurements on a metric (its canonical name), in graph order. */
export function measurementsOn(graph: GraphIndex, doc: string, canonical: string | null | undefined): EvGraphNode[] {
  const all = graph.inDocument(doc).filter((n) => n.type === "measurement")
  if (!canonical) return all
  return all.filter((m) => fieldOf(graph.node(linksOf(m).metric), "canonical") === canonical)
}

const whyItem = (graph: GraphIndex, role: string, id: string): WhyStep => ({ role, text: nodeText(graph.node(id)), item: id, foundBy: graph.foundBy([id]) })

export const INVENTORY_LANES: Lane[] = [
  { key: "several", label: "in several papers", tone: "good", hint: "more than one paper names it" },
  { key: "single", label: "in one paper", tone: "neutral", hint: "only one paper names it" },
]

export interface InventoryData {
  entry: InventoryAnswer["entries"][number]
  /** per paper, the entry's items in it (the panel highlights them) */
  papers: { document: string; items: string[]; target: SourceTarget }[]
  foundBy: string[]
}

/** One row per entry (a distinct name), its papers each opening that paper with the entry's items marked. */
export function inventoryRows(answer: InventoryAnswer, graph: GraphIndex): EvidenceRow<InventoryData>[] {
  return answer.entries.map((entry, n) => {
    const lane = entry.papers.length > 1 ? "several" : "single"
    const key = `${entry.name}#${n}`
    const papers = entry.papers.map((document) => {
      const own = entry.items.filter((i) => graph.node(i)?.document === document)
      const items = own.length ? own : entry.items
      const why: WhyStep[] = [
        { role: answer.target ?? "name", text: entry.name },
        ...(entry.aliases.length ? [{ role: "other names", text: entry.aliases.join(", ") }] : []),
        ...own.map((i) => whyItem(graph, "item", i)),
      ]
      return { document, items, target: { key, document, title: document, lane, items, focus: items[0] ?? null, why } }
    })
    return { key, document: null, lane, target: papers[0]?.target ?? null, data: { entry, papers, foundBy: graph.foundBy(entry.items) } }
  })
}

/** The run's papers in which no entry was found (an inventory's "left out"). */
export function inventoryMissing(answer: InventoryAnswer, documents: string[]): string[] {
  const named = new Set(answer.entries.flatMap((e) => e.papers))
  return documents.filter((d) => !named.has(d))
}

export const CONSISTENCY_LANES: Lane[] = [
  { key: "agrees", label: "agrees", tone: "good", hint: "the authors claim what their numbers show" },
  { key: "disagrees", label: "disagrees", tone: "critical", hint: "the authors claim something their numbers do not show" },
  { key: "undetermined", label: "undetermined", tone: "warning", hint: "no claim, or no numbers to check it against" },
  { key: "absent", label: "not in the answer", tone: "neutral", hint: "the system did not use this paper", muted: true },
]

export interface ConsistencyData {
  study: ConsistencyAnswer["studies"][number] | null
  claimItem: string | null
  numberItems: string[]
  foundBy: string[]
}

const allDocs = (documents: string[], studies: { document: string }[]) =>
  [...documents, ...studies.map((s) => s.document).filter((d) => !documents.includes(d))]

/** One row per paper: what the paper claims, what its numbers say (on the answer's metric), whether they agree. */
export function consistencyRows(answer: ConsistencyAnswer, documents: string[], graph: GraphIndex): EvidenceRow<ConsistencyData>[] {
  const studies = new Map(answer.studies.map((s) => [s.document, s]))
  return allDocs(documents, answer.studies).map((doc) => {
    const study = studies.get(doc) ?? null
    const lane = !study ? "absent" : study.agrees === true ? "agrees" : study.agrees === false ? "disagrees" : "undetermined"
    const claimItem = graph.inDocument(doc).find((n) => n.type === "author_claim")?.id ?? null
    const numberItems = measurementsOn(graph, doc, answer.metric).map((m) => m.id)
    const items = [...(claimItem ? [claimItem] : []), ...numberItems]
    const rule = !study ? "not in the answer"
      : study.agrees === null || study.agrees === undefined ? (study.reason?.text ?? study.reason?.code ?? "nothing to compare")
        : `the claim "${study.claim}" ${study.agrees ? "matches" : "does not match"} what the numbers show (${study.direction})`
    const why: WhyStep[] = [
      claimItem ? whyItem(graph, "paper says", claimItem) : { role: "paper says", text: study?.claim ?? "no claim found" },
      ...numberItems.map((i) => whyItem(graph, `numbers${answer.metric ? ` (${answer.metric})` : ""}`, i)),
      { role: "rule", text: rule },
    ]
    return {
      key: doc, document: doc, lane,
      target: { key: doc, document: doc, title: doc, lane, items, focus: claimItem ?? numberItems[0] ?? null, why },
      data: { study, claimItem, numberItems, foundBy: graph.foundBy(items) },
    }
  })
}

export const BEST_LANES: Lane[] = [
  { key: "winner", label: "has a winner", tone: "good", hint: "one method kind has the top value" },
  { key: "tie", label: "tie", tone: "neutral", hint: "several kinds share the top value" },
  { key: "undetermined", label: "undetermined", tone: "warning", hint: "fewer than two kinds measured on the metric" },
  { key: "absent", label: "not in the answer", tone: "neutral", hint: "the system did not use this paper", muted: true },
]

export interface BestData {
  study: BestAnswer["studies"][number] | null
  /** per method kind, its value and the measurement it was read from (matched by metric and value) */
  values: Record<string, { value: number; item: string | null }>
  foundBy: string[]
}

/**
 * The measurement a best study's value came from: answer.json keeps only the number, so the paper's
 * measurement on the metric with that value, preferring one whose condition is of that kind (its `kind`
 * field, or its label among the protocol's names for the kind).
 */
function bestItem(graph: GraphIndex, doc: string, metric: string | null | undefined, kind: string, value: number, names?: string[]): string | null {
  const same = measurementsOn(graph, doc, metric).filter((m) => fieldOf(m, "value") === value)
  const ofKind = same.find((m) => {
    const cond = graph.node(linksOf(m).condition)
    return fieldOf(cond, "kind") === kind || (names ?? []).some((n) => fold(n) === fold(fieldOf(cond, "label")))
  })
  return (ofKind ?? same[0])?.id ?? null
}

/** One row per paper: the value of each method kind on the metric and which kind wins inside the paper. */
export function bestRows(answer: BestAnswer, documents: string[], graph: GraphIndex, kinds?: Record<string, string[]> | null): EvidenceRow<BestData>[] {
  const studies = new Map(answer.studies.map((s) => [s.document, s]))
  return allDocs(documents, answer.studies).map((doc) => {
    const study = studies.get(doc) ?? null
    const lane = !study ? "absent" : study.winner ? "winner" : study.tied.length ? "tie" : "undetermined"
    const values = Object.fromEntries(Object.entries(study?.values ?? {})
      .map(([k, v]) => [k, { value: v, item: bestItem(graph, doc, answer.metric, k, v, kinds?.[k]) }]))
    const items = Object.values(values).map((v) => v.item).filter((x): x is string => !!x)
    const top = study?.winner ?? study?.tied[0] ?? null
    const rule = !study ? "not in the answer"
      : lane === "undetermined" ? (study.reason?.text ?? study.reason?.code ?? "no comparison")
        : `${lane === "tie" ? `${study.tied.join(", ")} share` : `${study.winner} has`} the top value on ${answer.metric ?? "the metric"}`
    const why: WhyStep[] = [
      ...Object.entries(values).map(([k, v]) => ({ role: k, text: num(v.value, 3), item: v.item, foundBy: graph.foundBy([v.item, linksOf(graph.node(v.item)).condition]) })),
      { role: "rule", text: rule },
    ]
    return {
      key: doc, document: doc, lane,
      target: { key: doc, document: doc, title: doc, lane, items, focus: (top ? values[top]?.item : null) ?? items[0] ?? null, why },
      data: { study, values, foundBy: graph.foundBy(items) },
    }
  })
}
