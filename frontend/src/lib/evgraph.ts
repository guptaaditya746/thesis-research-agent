/**
 * A run's graph -> React Flow nodes and edges, laid out by dagre. The server sends one of two graphs (`source`):
 *
 * - `records` (a plan run): the RDF records graph its answer was computed from (records.nq, evidence/kg/view.py).
 *   Nodes are papers, experiments, things, metrics, values, claims, links, comparisons and the ontology classes the
 *   records are typed with; `type` is the node's ev: type (or Class), edges are the properties between them (`rel` is
 *   the property's local name: inPaper, inExperiment, of, onMetric, a, b, better, cites, type, subClassOf). Things,
 *   metrics and classes are shared by papers (no `document`): a document filter keeps a paper's nodes and the shared
 *   nodes they touch.
 * - `evidence` (any other run): the engine's evidence graph (graph.json, evidence/graph.py). Nodes are the documents
 *   and the merged evidence items; edges `in_document` (item -> its paper), `condition` and `metric` (a measurement
 *   -> the items it links), `supports` / `contradicts` (the treatment measurement a study's effect rests on -> the
 *   control measurement, as synthesis decided) and `duplicate_of` (paper -> the earlier paper it repeats).
 *   `in_document` edges are many and say little once the nodes sit in their paper's column, so they are optional
 *   (`withDocumentEdges`). A document filter keeps one paper's items (and the duplicate edges that touch it).
 */
import dagre from "@dagrejs/dagre"
import type { Edge, Node } from "@xyflow/react"

import type { EvGraph, EvGraphNode } from "@/api/ev"

import { itemLabel, typeLabel, typeTag, TYPE_COLOR } from "./ev"

export type GraphSource = "evidence" | "records"
export type EvNodeData = { label: string; type: string; document: string | null; foundBy: string[]; source: GraphSource; types: string[] }
export type EvEdgeData = { rel: string }
export type EvFlowNode = Node<EvNodeData, "evidence">
export type EvFlowEdge = Edge<EvEdgeData>

export const EV_NODE_HEIGHT = 40
/** Edges laid out target first, so a paper sits left of its items (evidence) or of its experiments and values (records). */
const REVERSED = new Set(["in_document", "condition", "metric", "inPaper", "inExperiment", "a", "b", "better"])

/** The record types of the records graph, in legend order, each with a colour and a short tag. */
export const RECORD_TYPES = ["Paper", "Experiment", "Thing", "Metric", "Value", "Claim", "Link", "Comparison", "Class"] as const
const RECORD_COLOR: Record<string, string> = {
  Paper: "var(--foreground)",
  Experiment: "var(--chart-2)",
  Thing: "var(--chart-1)",
  Metric: "var(--chart-4)",
  Value: "var(--chart-3)",
  Claim: "var(--chart-5)",
  Link: "var(--muted-foreground)",
  Comparison: "var(--muted-foreground)",
  Class: "var(--status-warning-fg)",
}
const RECORD_TAG: Record<string, string> = {
  Paper: "paper", Experiment: "exp", Thing: "thing", Metric: "metric", Value: "value", Claim: "claim", Link: "link",
  Comparison: "cmp", Class: "class",
}
const RECORD_LABEL: Record<string, string> = { Class: "ontology class" }

/** A node type's tag, name and colour, by the graph it comes from. */
export const nodeTag = (source: GraphSource, type: string) => (source === "records" ? RECORD_TAG[type] ?? type.slice(0, 6).toLowerCase() : typeTag(type))
export const nodeTypeLabel = (source: GraphSource, type: string) => (source === "records" ? RECORD_LABEL[type] ?? type.toLowerCase() : typeLabel(type))
export const nodeColor = (source: GraphSource, type: string) => (source === "records" ? RECORD_COLOR[type] ?? "var(--muted-foreground)" : TYPE_COLOR[type])

/** Label plus padding plus the type tag (or the paper icon), which takes about its letters at text-xs. */
export const evNodeWidth = (label: string, type = "", source: GraphSource = "evidence") => {
  const paper = source === "records" ? type === "Paper" : type === "document"
  return Math.min(320, Math.max(96, Math.round(label.length * 7 + 40 + (paper ? 0 : nodeTag(source, type).length * 7 + 14))))
}

export function nodeLabel(node: EvGraphNode, source: GraphSource = "evidence"): string {
  if (source === "records") return node.label ?? node.id
  if (node.type === "document") return node.id
  return itemLabel({ evidence_type: node.type as never, fields: (node.fields ?? {}) as Record<string, unknown> })
}

export interface EvGraphOptions {
  /** keep only this document's nodes */
  document?: string | null
  /** draw item -> paper edges too (evidence graph) */
  withDocumentEdges?: boolean
}

export const graphSource = (graph: EvGraph): GraphSource => (graph.source === "records" ? "records" : "evidence")

/** The nodes a document filter keeps: the paper's own, and (records graph) the shared nodes they touch and their classes. */
function keptNodes(graph: EvGraph, source: GraphSource, document: string | null): EvGraphNode[] {
  if (!document) return graph.nodes
  const own = (n: EvGraphNode) => n.id === document || n.document === document
  if (source === "evidence") return graph.nodes.filter(own)
  const mine = new Set(graph.nodes.filter(own).map((n) => n.id))
  const touched = new Set<string>()
  for (const e of graph.edges) {
    if (mine.has(e.src)) touched.add(e.dst)
    if (mine.has(e.dst)) touched.add(e.src)
  }
  const kept = new Set([...mine, ...graph.nodes.filter((n) => !n.document && touched.has(n.id)).map((n) => n.id)])
  // and the ontology classes of what is kept, up their subClassOf chain
  for (let grew = true; grew;) {
    grew = false
    for (const e of graph.edges) {
      if ((e.rel === "type" || e.rel === "subClassOf") && kept.has(e.src) && !kept.has(e.dst)) {
        kept.add(e.dst)
        grew = true
      }
    }
  }
  return graph.nodes.filter((n) => kept.has(n.id))
}

/** Nodes and edges of the graph, positioned; edges whose ends are not shown are left out and counted. */
export function toEvFlow(graph: EvGraph, { document = null, withDocumentEdges = false }: EvGraphOptions = {}) {
  const source = graphSource(graph)
  const kept = keptNodes(graph, source, document)
  const ids = new Set(kept.map((n) => n.id))
  let hidden = 0
  const edges: EvFlowEdge[] = []
  for (const e of graph.edges) {
    if (e.rel === "in_document" && !withDocumentEdges) continue
    if (!ids.has(e.src) || !ids.has(e.dst)) {
      hidden += 1
      continue
    }
    edges.push({ id: `${e.src}|${e.rel}|${e.dst}`, source: e.src, target: e.dst, data: { rel: e.rel }, label: e.rel === "in_document" ? undefined : e.rel })
  }
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 56, marginx: 8, marginy: 8 })
  g.setDefaultEdgeLabel(() => ({}))
  const nodes: EvFlowNode[] = kept.map((n) => {
    const label = nodeLabel(n, source)
    g.setNode(n.id, { width: evNodeWidth(label, n.type, source), height: EV_NODE_HEIGHT })
    const paper = source === "records" ? n.type === "Paper" : n.type === "document"
    return {
      id: n.id,
      type: "evidence",
      position: { x: 0, y: 0 },
      data: {
        label, type: n.type, source, types: n.types ?? [], foundBy: n.found_by ?? [],
        document: n.document ?? (paper && source === "evidence" ? n.id : null),
      },
    }
  })
  // Layout from every edge between shown nodes, drawn or not, so items sit beside their paper. The paper,
  // then conditions and metrics, then the measurements that link them: links are laid out target first.
  for (const e of graph.edges) {
    if (!ids.has(e.src) || !ids.has(e.dst)) continue
    if (REVERSED.has(e.rel)) g.setEdge(e.dst, e.src)
    else g.setEdge(e.src, e.dst)
  }
  dagre.layout(g)
  for (const node of nodes) {
    const at = g.node(node.id)
    node.position = { x: at.x - at.width / 2, y: at.y - at.height / 2 }
  }
  return { nodes, edges, hidden, source }
}
