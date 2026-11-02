/**
 * The readable evidence graph: Papers -> Claims -> Verdict, three columns (src/components/ev/ClaimGraph.tsx).
 *
 * A claim is one thing the answer rests on, read from answer.json by `claimsOf` (the one place that knows each
 * kind's answer shape): a determined study with both sides' values (effect, best), a study whose authors' claim
 * was checked (consistency), a limitation entry, a dependency link (builds_on) or a chain step (chaining). Each
 * claim has edges from the papers it is read from and one edge to the verdict, the answer's text and the rule
 * that decided it. Edge kinds are told by colour and by line and always by a text label: supports (good, solid),
 * contradicts (critical, solid), neutral (muted), builds on and inferred chain steps (dashed "6 4").
 *
 * The items under a claim (conditions, metrics, measurements) are not nodes; `claimItems` lists them for the
 * claim's sheet. dagre orders the rows (fewer crossings); the x of every node is pinned by its column.
 */
import dagre from "@dagrejs/dagre"
import type { Edge, Node } from "@xyflow/react"

import type { BestAnswer, BuildsOnAnswer, ChainingAnswer, ConsistencyAnswer, EvGraph, EvGraphNode, LimitationsAnswer, RunAnswer } from "@/api/ev"

import { answerHeadline, effectAnswer } from "./ev"

/** What a claim says about the verdict: the claim -> verdict edge's kind. */
export type ClaimRel = "supports" | "contradicts" | "neutral" | "builds_on" | "chain"
export type Column = "paper" | "claim" | "verdict"
/** The pack's display names (EvRunDetail.display): `treatment` and `control` name the two sides. */
export type Display = Record<string, string>

export interface Claim {
  id: string
  label: string
  /** the papers the claim is read from, each with the words on its paper -> claim edge */
  sources: { document: string; label: string }[]
  /** ids of the items (graph nodes) it rests on; empty when the answer names none (best, consistency, chaining) */
  items: string[]
  rel: ClaimRel
  /** the words on the claim -> verdict edge */
  edgeLabel: string
  /** a line for the claim's sheet when it names no items (a chain step's comparison) */
  detail?: string
}

export type ClaimNodeData = { label: string; column: Column; type: string; claim?: Claim; rule?: string }
export type ClaimEdgeData = { rel: string }
export type ClaimFlowNode = Node<ClaimNodeData, "claim">
export type ClaimFlowEdge = Edge<ClaimEdgeData>

export const CLAIM_NODE_HEIGHT = 40
export const VERDICT_NODE_HEIGHT = 56
const COLUMN_GAP = 96
export const claimNodeWidth = (label: string, column: Column) =>
  column === "paper" ? Math.min(200, Math.max(80, label.length * 7 + 40)) : Math.min(360, Math.max(120, label.length * 7 + 24))

/** Each edge kind's colour and dash; `from` is a paper -> claim edge. */
export const CLAIM_EDGE_STYLE: Record<ClaimRel | "from", { color: string; dash?: string; width: number }> = {
  supports: { color: "var(--status-good)", width: 2 },
  contradicts: { color: "var(--status-critical)", width: 2 },
  neutral: { color: "var(--muted-foreground)", width: 2 },
  builds_on: { color: "var(--muted-foreground)", dash: "6 4", width: 2 },
  chain: { color: "var(--muted-foreground)", dash: "6 4", width: 2 },
  from: { color: "var(--muted-foreground)", width: 1 },
}

const words = (code: string) => code.replaceAll("_", " ")
const value = (v: number) => (Number.isInteger(v) ? String(v) : String(Number(v.toFixed(3))))
/** "better than", "worse than", "no different from": a chain step's or verdict's direction as words. */
const ORDER_WORDS: Record<string, string> = { better: "better than", worse: "worse than", no_difference: "no different from" }
const ORDER_REL: Record<string, ClaimRel> = { better: "supports", worse: "contradicts", no_difference: "neutral" }

/** The claims of an answer, one case per kind; `display` names the two sides of an effect or consistency claim. */
export function claimsOf(answer: RunAnswer, kind: string, display: Display = {}): Claim[] {
  const side = (key: "treatment" | "control") => display[key] ?? key
  const name = (thing: string) => display[thing] ?? thing
  const claims: Omit<Claim, "id">[] = []
  switch (kind) {
    case "effect": {
      for (const s of effectAnswer(answer)?.studies ?? []) {
        const t = s.treatment?.value
        const c = s.control?.value
        if (s.direction === "undetermined" || t === null || t === undefined || c === null || c === undefined) continue
        claims.push({
          label: `${side("treatment")} ${value(t)} vs ${side("control")} ${value(c)} on ${s.metric ?? "the metric"}`,
          sources: [{ document: s.document, label: "reports" }],
          items: [s.treatment?.measurement, s.control?.measurement].filter((i): i is string => !!i),
          rel: s.direction, edgeLabel: s.direction,
        })
      }
      break
    }
    case "best": {
      const a = answer as BestAnswer
      for (const s of a.studies) {
        const top = s.winner ?? s.tied[0]
        const at = top === undefined ? undefined : s.values[top]
        if (top === undefined || at === undefined) continue
        // the other side is the closest rival: the runner-up, whichever way the metric points
        const rival = Object.entries(s.values).filter(([k]) => k !== top).sort((x, y) => Math.abs(x[1] - at) - Math.abs(y[1] - at))[0]
        if (!rival) continue
        const rel: ClaimRel = !s.winner || !a.winner ? "neutral" : s.winner === a.winner ? "supports" : "contradicts"
        claims.push({
          label: `${name(top)} ${value(at)} vs ${name(rival[0])} ${value(rival[1])} on ${a.metric ?? "the metric"}`,
          sources: [{ document: s.document, label: "reports" }], items: [],
          rel, edgeLabel: s.winner ? (rel === "neutral" ? `${name(s.winner)} wins` : rel) : "tie",
        })
      }
      break
    }
    case "consistency": {
      const a = answer as ConsistencyAnswer
      for (const s of a.studies) {
        if (s.agrees === null || s.agrees === undefined || !s.direction) continue
        claims.push({
          label: `${side("treatment")} vs ${side("control")} on ${a.metric ?? "the metric"}: measured ${s.direction}, authors claim ${s.claim ?? "nothing"}`,
          sources: [{ document: s.document, label: "reports" }], items: [],
          rel: s.agrees ? "supports" : "contradicts", edgeLabel: s.agrees ? "claim agrees" : "claim disagrees",
        })
      }
      break
    }
    case "limitations": {
      for (const e of (answer as LimitationsAnswer).entries) {
        claims.push({
          label: `${e.thing ?? "no compared thing named"}: ${words(e.category)}`,
          sources: e.papers.map((d) => ({ document: d, label: "states" })), items: e.items,
          rel: "neutral", edgeLabel: `${e.papers.length} paper${e.papers.length === 1 ? "" : "s"}`,
        })
      }
      break
    }
    case "builds_on": {
      for (const l of (answer as BuildsOnAnswer).links) {
        claims.push({
          label: `${l.from} builds on ${l.to} (${words(l.reuses)})`,
          sources: l.from === l.to ? [{ document: l.from, label: "cites" }] : [{ document: l.from, label: "cites" }, { document: l.to, label: "is cited" }],
          items: l.items, rel: "builds_on", edgeLabel: "builds on",
        })
      }
      break
    }
    case "chaining": {
      const seen = new Set<string>()
      for (const path of (answer as ChainingAnswer).paths) {
        for (const st of path.steps) {
          const key = `${st.comparison}|${st.from}|${st.to}`
          if (seen.has(key)) continue
          seen.add(key)
          const chained = path.via.length > 0
          claims.push({
            label: `${st.from} ${ORDER_WORDS[st.direction ?? ""] ?? "vs"} ${st.to} on ${st.metric ?? "the metric"}`,
            sources: [{ document: st.document, label: "reports" }], items: [],
            rel: chained ? "chain" : ORDER_REL[st.direction ?? ""] ?? "neutral",
            edgeLabel: chained ? `inferred through ${path.via.join(", ")}` : "direct result",
            detail: `comparison ${st.comparison}${st.context ? `, in ${st.context}` : ""}`,
          })
        }
      }
      break
    }
  }
  return claims.map((c, n) => ({ ...c, id: `claim-${n}` }))
}

/** The verdict node: the kind's answer as text, and the rule that decided it. */
export function verdictOf(answer: RunAnswer, kind: string): { text: string; rule: string } {
  switch (kind) {
    case "effect": return { text: effectAnswer(answer)?.label ?? "no label", rule: "the label table over the study counts" }
    case "best": return { text: answerHeadline(answer), rule: "the kind that wins the most papers" }
    case "consistency": return { text: answerHeadline(answer), rule: "the authors' claim against the measured direction" }
    case "limitations": {
      const n = (answer as LimitationsAnswer).entries.length
      return { text: `${n} limitation${n === 1 ? "" : "s"} listed`, rule: "grouped by compared thing and category" }
    }
    case "builds_on": {
      const top = (answer as BuildsOnAnswer).ranking[0]
      return { text: top ? `most built on: ${top}` : "nothing is built on", rule: "influence: the papers that build on a thing's origin" }
    }
    case "chaining": {
      const a = answer as ChainingAnswer
      const text = a.verdict === "refused" ? `no answer for ${a.source} vs ${a.target}` : `${a.source} ${ORDER_WORDS[a.verdict] ?? a.verdict} ${a.target}`
      return { text, rule: a.reason ? words(a.reason) : a.note ?? "every step of the chain agrees" }
    }
    default: return { text: answerHeadline(answer), rule: `kind ${kind}` }
  }
}

/** A claim's items in the graph: each item it names, then the items that one links (its condition, metric). */
export function claimItems(graph: EvGraph, claim: Claim): EvGraphNode[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const out = new Map<string, EvGraphNode>()
  for (const id of claim.items) {
    const item = byId.get(id)
    if (!item) continue
    out.set(id, item)
    for (const target of Object.values((item.links ?? {}) as Record<string, string>)) {
      const linked = byId.get(target)
      if (linked && !out.has(target)) out.set(target, linked)
    }
  }
  return [...out.values()]
}

/** Nodes (papers, claims, the verdict) and edges, positioned: x by column, rows by dagre. */
export function toClaimFlow(graph: EvGraph, answer: RunAnswer, kind: string, display: Display = {}) {
  const claims = claimsOf(answer, kind, display)
  const verdict = verdictOf(answer, kind)
  const papers = [...new Set([...graph.nodes.filter((n) => n.type === "document").map((n) => n.id),
    ...claims.flatMap((c) => c.sources.map((s) => s.document))])]
  const nodes: ClaimFlowNode[] = [
    ...papers.map((id): ClaimFlowNode => ({ id: `paper:${id}`, type: "claim", position: { x: 0, y: 0 }, data: { label: id, column: "paper", type: "document" } })),
    ...claims.map((c): ClaimFlowNode => ({ id: c.id, type: "claim", position: { x: 0, y: 0 }, data: { label: c.label, column: "claim", type: "claim", claim: c } })),
    { id: "verdict", type: "claim", position: { x: 0, y: 0 }, data: { label: verdict.text, column: "verdict", type: "verdict", rule: verdict.rule } },
  ]
  const edge = (source: string, target: string, rel: ClaimRel | "from", label: string): ClaimFlowEdge => {
    const style = CLAIM_EDGE_STYLE[rel]
    return {
      id: `${source}|${rel}|${target}`, source, target, label, data: { rel },
      style: { stroke: style.color, strokeWidth: style.width, strokeDasharray: style.dash },
    }
  }
  const edges: ClaimFlowEdge[] = [
    ...claims.flatMap((c) => c.sources.map((s) => edge(`paper:${s.document}`, c.id, "from", s.label))),
    ...claims.map((c) => edge(c.id, "verdict", c.rel, c.edgeLabel)),
  ]
  const height = (n: ClaimFlowNode) => (n.data.column === "verdict" ? VERDICT_NODE_HEIGHT : CLAIM_NODE_HEIGHT)
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: COLUMN_GAP, marginx: 8, marginy: 8 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const n of nodes) g.setNode(n.id, { width: claimNodeWidth(n.data.label, n.data.column), height: height(n) })
  for (const e of edges) g.setEdge(e.source, e.target)
  dagre.layout(g)
  // A paper without a claim would sit in dagre's first rank anyway; pinning x keeps every column straight.
  const widest = (column: Column) => Math.max(0, ...nodes.filter((n) => n.data.column === column).map((n) => claimNodeWidth(n.data.label, column)))
  const left: Record<Column, number> = { paper: 0, claim: widest("paper") + COLUMN_GAP, verdict: widest("paper") + widest("claim") + 2 * COLUMN_GAP }
  for (const n of nodes) {
    const at = g.node(n.id)
    n.position = { x: left[n.data.column], y: at.y - at.height / 2 }
  }
  return { nodes, edges, claims, verdict }
}
