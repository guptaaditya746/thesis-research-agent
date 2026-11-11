/**
 * The run's graph in React Flow, laid out by dagre (src/lib/evgraph.ts). A plan run shows its records graph (the
 * RDF graph its answer was computed from): papers, experiments, things, metrics, values, claims, links, comparisons
 * and ontology classes, each with its type as a tag and border colour, edges named by their property. Any other run
 * shows its evidence graph (graph.json): papers and the merged items, with the links between them and the
 * supports / contradicts edge of every determined study (contradicts dashed, so not told by colour alone).
 * One paper at a time by default (a whole corpus is hundreds of nodes); with `paperHref`, clicking a node
 * opens its paper. Below the canvas the same nodes and edges as lists, for keyboard use and screen readers.
 */
import "@xyflow/react/dist/style.css"

import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type NodeMouseHandler, type NodeProps } from "@xyflow/react"
import { FileTextIcon, NetworkIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useCallback, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router"

import type { EvGraph } from "@/api/ev"
import { EmptyState } from "@/components/states"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { EVIDENCE_TYPES, TYPE_COLOR, typeLabel, typeTag } from "@/lib/ev"
import { EV_NODE_HEIGHT, evNodeWidth, graphSource, nodeColor, nodeTag, nodeTypeLabel, RECORD_TYPES, toEvFlow, type EvFlowNode } from "@/lib/evgraph"

import { MarkLegend, type LegendEntry } from "./PaperText"

/** The node's type in words, with its other rdf:types (ontology classes) on a records graph. */
const describe = (d: EvFlowNode["data"]) =>
  `${nodeTypeLabel(d.source, d.type)}: ${d.label}${d.types.length > 1 ? ` (${d.types.join(", ")})` : ""}`

function EvidenceNode({ data }: NodeProps<EvFlowNode>) {
  const paper = data.source === "records" ? data.type === "Paper" : data.type === "document"
  return (
    <div
      className="flex items-center gap-1.5 rounded-md border-2 bg-card px-2 text-xs shadow-sm"
      style={{ width: evNodeWidth(data.label, data.type, data.source), height: EV_NODE_HEIGHT, borderColor: paper ? "var(--foreground)" : nodeColor(data.source, data.type) }}
      title={`${describe(data)}${data.foundBy.length ? `\nfound by ${data.foundBy.join(", ")}` : ""}`}
    >
      {paper
        ? <FileTextIcon className="size-3.5 shrink-0" aria-hidden="true" />
        : <span className="shrink-0 rounded-sm bg-muted px-1 font-medium text-muted-foreground" aria-hidden="true">{nodeTag(data.source, data.type)}</span>}
      <span className="truncate">{data.label}</span>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-muted-foreground" />
    </div>
  )
}

const NODE_TYPES = { evidence: EvidenceNode }
/** Edge kinds by colour and line style, so red against green is never the only cue. */
const EDGE_STYLE: Record<string, { color: string; dash?: string; line: LegendEntry["line"]; label: string }> = {
  supports: { color: "var(--status-good)", line: "solid", label: "supports" },
  contradicts: { color: "var(--status-critical)", dash: "6 4", line: "dashed", label: "contradicts" },
  duplicate_of: { color: "var(--status-warning-fg)", dash: "2 3", line: "dotted", label: "duplicate of" },
}
const LEGEND: LegendEntry[] = [
  ...EVIDENCE_TYPES.map((t) => ({ label: `${typeLabel(t)} (${typeTag(t)})`, color: TYPE_COLOR[t] })),
  ...Object.values(EDGE_STYLE).map((e) => ({ label: `${e.label} edge`, color: e.color, line: e.line })),
]
const RECORDS_LEGEND: LegendEntry[] = RECORD_TYPES.filter((t) => t !== "Paper")
  .map((t) => ({ label: `${nodeTypeLabel("records", t)} (${nodeTag("records", t)})`, color: nodeColor("records", t) }))

export function EvidenceGraph({ graph, documents, paperHref }: {
  graph: EvGraph
  documents: string[]
  /** where a node's paper opens (the run's paper view); without it nodes do not navigate */
  paperHref?: (doc: string) => string
}) {
  const { resolvedTheme } = useTheme()
  const navigate = useNavigate()
  const [document, setDocument] = useState<string>(documents[0] ?? "__all")
  const [withDocs, setWithDocs] = useState(false)
  const flow = useMemo(() => toEvFlow(graph, { document: document === "__all" ? null : document, withDocumentEdges: withDocs }),
    [graph, document, withDocs])
  const records = graphSource(graph) === "records"
  const byId = useMemo(() => new Map(flow.nodes.map((n) => [n.id, n.data])), [flow])
  // Screen readers announce a node by its aria-label (the tag is aria-hidden: the label says the type in full).
  const nodes = useMemo(() => flow.nodes.map((n) => ({
    ...n,
    className: paperHref && n.data.document ? "cursor-pointer" : undefined,
    ariaLabel: `${describe(n.data)}${n.data.foundBy.length ? `, found by ${n.data.foundBy.join(", ")}` : ""}`,
  })), [flow, paperHref])
  const edges = useMemo(() => flow.edges.map((e) => {
    const kind = EDGE_STYLE[e.data?.rel ?? ""]
    return {
      ...e,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: kind?.color ?? "var(--muted-foreground)", strokeWidth: kind ? 2 : 1, strokeDasharray: kind?.dash },
      labelStyle: { fontSize: 11 },
    }
  }), [flow])
  const onNodeClick = useCallback<NodeMouseHandler<EvFlowNode>>((_, node) => {
    if (paperHref && node.data.document) void navigate(paperHref(node.data.document))
  }, [navigate, paperHref])
  const name = (id: string) => {
    const d = byId.get(id)
    return d ? `${nodeTypeLabel(d.source, d.type)} ${d.label}` : id
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Label htmlFor="graph-doc" className="text-sm">Paper</Label>
          <Select value={document} onValueChange={setDocument}>
            <SelectTrigger id="graph-doc" className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">all papers</SelectItem>
              {documents.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {!records && (
          <div className="flex items-center gap-2">
            <Switch id="graph-docs" checked={withDocs} onCheckedChange={setWithDocs} />
            <Label htmlFor="graph-docs" className="text-sm">item → paper edges</Label>
          </div>
        )}
        <span className="text-xs text-muted-foreground">
          {records ? "Records graph (what the answer was computed from): " : ""}
          {flow.nodes.length} nodes, {flow.edges.length} edges{flow.hidden ? `, ${flow.hidden} to other papers not shown` : ""}
          {records && Object.keys(graph.omitted ?? {}).length > 0
            ? `; left out to keep it drawable: ${Object.entries(graph.omitted ?? {}).map(([t, n]) => `${n} ${nodeTypeLabel("records", t)}`).join(", ")}`
            : ""}
        </span>
      </div>
      <MarkLegend entries={records ? RECORDS_LEGEND : LEGEND} overlap={false} label="Legend" />
      {flow.nodes.length === 0 ? (
        <EmptyState icon={<NetworkIcon />} title={document === "__all" ? "No evidence items in this run" : "No evidence items in this paper"}
          description={document === "__all" ? undefined : "The engine kept no item from it; choose another paper above."} />
      ) : (
        // role="group", not "img": an image role would hide the zoom controls and nodes from screen readers
        <div className="h-[60vh] rounded-md border" role="group" aria-label={`Evidence graph${document !== "__all" ? ` of ${document}` : ""}`}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodeClick={onNodeClick} fitView minZoom={0.1} nodesDraggable={false}
            colorMode={resolvedTheme === "dark" ? "dark" : "light"} proOptions={{ hideAttribution: true }}>
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      )}
      {flow.nodes.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm">Nodes and edges as lists</summary>
          <div className="mt-2 grid gap-4 text-xs lg:grid-cols-2">
            <ul className="space-y-0.5" aria-label="Nodes">
              {flow.nodes.map((n) => (
                <li key={n.id}>
                  <span className="text-muted-foreground">{nodeTypeLabel(n.data.source, n.data.type)}:</span>{" "}
                  {paperHref && n.data.document
                    ? <Link to={paperHref(n.data.document)} className="underline underline-offset-2">{n.data.label}</Link>
                    : n.data.label}
                  {n.data.foundBy.length > 0 && <span className="text-muted-foreground"> · found by {n.data.foundBy.join(", ")}</span>}
                </li>
              ))}
            </ul>
            <ul className="space-y-0.5" aria-label="Edges">
              {flow.edges.map((e) => (
                <li key={e.id}>
                  {name(e.source)} —{e.data?.rel}→ {name(e.target)}
                </li>
              ))}
            </ul>
          </div>
        </details>
      )}
    </div>
  )
}
