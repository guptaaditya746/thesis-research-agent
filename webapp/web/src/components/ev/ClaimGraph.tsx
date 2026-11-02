/**
 * The run's evidence graph as three columns, Papers -> Claims -> Verdict (src/lib/claimgraph.ts), in React Flow.
 * A claim is one thing the answer rests on (a determined study, a limitation, a dependency, a chain step); its
 * edge to the verdict says how (supports, contradicts, builds on, inferred through ...), in words as well as
 * colour. Clicking a claim, on the canvas or in the lists below it, opens a sheet with the items it rests on,
 * each opening its paper with that item marked. Below the canvas the same nodes and edges as lists, for keyboard
 * use and screen readers.
 *
 * What the raw graph (EvidenceGraph.tsx, src/lib/evgraph.ts; still behind the run page's "raw items" switch)
 * shows that this one drops, from reading it on an engine run of the test world (cascade on the explicit corpus:
 * 27 nodes for six papers, 21 items; 27 edges, of which 21 are item -> paper and 6 measurement -> condition/metric):
 * - `in_document` edges (item -> its paper) and the switch that drew them: a claim's paper edge says the same;
 * - condition, metric, measurement and author-claim nodes, and the `condition` / `metric` edges between them:
 *   they are the claim's items, listed in its sheet, not nodes;
 * - the per-paper selector: every paper is one node, so the whole run fits on one canvas;
 * - the evidence-type legend and type tags (no item nodes left to tag);
 * - `duplicate_of` edges between papers (the Answer tab flags duplicates; the raw graph still draws them);
 * - `found_by` on the node: it is in the claim's sheet, per item.
 */
import "@xyflow/react/dist/style.css"

import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type NodeMouseHandler, type NodeProps } from "@xyflow/react"
import { FileTextIcon, NetworkIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useCallback, useMemo, useState } from "react"
import { Link } from "react-router"

import type { EvGraph, RunAnswer } from "@/api/ev"
import { EmptyState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { itemLabel, typeLabel } from "@/lib/ev"
import { CLAIM_EDGE_STYLE, CLAIM_NODE_HEIGHT, claimItems, claimNodeWidth, toClaimFlow, VERDICT_NODE_HEIGHT, type Claim, type ClaimFlowNode, type Display } from "@/lib/claimgraph"

import { MarkLegend, type LegendEntry } from "./PaperText"

function ClaimNode({ data }: NodeProps<ClaimFlowNode>) {
  const verdict = data.column === "verdict"
  return (
    <div
      className={`flex items-center gap-1.5 rounded-md border-2 bg-card px-2 text-xs shadow-sm ${data.column === "claim" ? "cursor-pointer" : ""}`}
      style={{ width: claimNodeWidth(data.label, data.column), height: verdict ? VERDICT_NODE_HEIGHT : CLAIM_NODE_HEIGHT, borderColor: verdict ? "var(--foreground)" : "var(--border)" }}
      title={verdict ? `${data.label}\nrule: ${data.rule ?? ""}` : data.label}
    >
      {data.column === "paper" && <FileTextIcon className="size-3.5 shrink-0" aria-hidden="true" />}
      {verdict
        ? <span className="min-w-0"><span className="block truncate font-medium">{data.label}</span><span className="block truncate text-muted-foreground">{data.rule}</span></span>
        : <span className="truncate">{data.label}</span>}
      {data.column !== "paper" && <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />}
      {data.column !== "verdict" && <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-muted-foreground" />}
    </div>
  )
}

const NODE_TYPES = { claim: ClaimNode }
const LEGEND: LegendEntry[] = [
  { label: "supports", color: CLAIM_EDGE_STYLE.supports.color, line: "solid" },
  { label: "contradicts", color: CLAIM_EDGE_STYLE.contradicts.color, line: "solid" },
  { label: "neutral", color: CLAIM_EDGE_STYLE.neutral.color, line: "solid" },
  { label: "builds on, inferred through (chain)", color: CLAIM_EDGE_STYLE.chain.color, line: "dashed" },
]
const COLUMNS = ["Papers", "Claims", "Verdict"]

function ClaimSheet({ graph, claim, itemHref, onClose }: {
  graph: EvGraph
  claim: Claim | null
  itemHref: (doc: string, item?: string) => string
  onClose: () => void
}) {
  const items = claim ? claimItems(graph, claim) : []
  return (
    <Sheet open={!!claim} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{claim?.label}</SheetTitle>
          <SheetDescription>The items this claim rests on; each opens its paper with the item marked.</SheetDescription>
        </SheetHeader>
        {claim && (
          <div className="space-y-3 px-4 pb-6 text-sm">
            {items.length > 0 ? (
              <ul className="space-y-1" aria-label="Items of the claim">
                {items.map((n) => {
                  const label = itemLabel({ evidence_type: n.type as never, fields: (n.fields ?? {}) as Record<string, unknown> })
                  return (
                    <li key={n.id}>
                      <span className="text-muted-foreground">{typeLabel(n.type)}:</span>{" "}
                      {n.document ? <Link to={itemHref(n.document, n.id)} className="underline underline-offset-2">{label}</Link> : label}
                      {n.found_by.length > 0 && <span className="text-muted-foreground"> · found by {n.found_by.join(", ")}</span>}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-muted-foreground">The answer names no items for this claim{claim.detail ? ` (${claim.detail})` : ""}; its papers are below.</p>
            )}
            <p>
              From:{" "}
              {claim.sources.map((s) => <Link key={s.document} to={itemHref(s.document)} className="mr-2 font-mono text-xs underline">{s.document}</Link>)}
            </p>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export function ClaimGraph({ graph, answer, kind, display, itemHref }: {
  graph: EvGraph
  answer: RunAnswer
  /** the answer's question kind (effect when answer.json has no `kind`) */
  kind: string
  display: Display
  /** where a paper opens, at one of its items when given (the run's paper view) */
  itemHref: (doc: string, item?: string) => string
}) {
  const { resolvedTheme } = useTheme()
  const [open, setOpen] = useState<Claim | null>(null)
  const flow = useMemo(() => toClaimFlow(graph, answer, kind, display), [graph, answer, kind, display])
  const byId = useMemo(() => new Map(flow.nodes.map((n) => [n.id, n.data])), [flow])
  const nodes = useMemo(() => flow.nodes.map((n) => ({
    ...n,
    ariaLabel: n.data.column === "verdict" ? `Verdict: ${n.data.label} (${n.data.rule ?? ""})` : `${n.data.column === "paper" ? "Paper" : "Claim"}: ${n.data.label}`,
  })), [flow])
  const edges = useMemo(() => flow.edges.map((e) => ({ ...e, markerEnd: { type: MarkerType.ArrowClosed }, labelStyle: { fontSize: 11 } })), [flow])
  const onNodeClick = useCallback<NodeMouseHandler<ClaimFlowNode>>((_, node) => {
    if (node.data.claim) setOpen(node.data.claim)
  }, [])
  const name = (id: string) => byId.get(id)?.label ?? id
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4">
        <MarkLegend entries={LEGEND} overlap={false} label="Legend" />
        <span className="text-xs text-muted-foreground">{flow.claims.length} claims from {flow.nodes.filter((n) => n.data.column === "paper").length} papers</span>
      </div>
      <div className="grid grid-cols-3 text-sm font-medium">
        {COLUMNS.map((c, n) => <h3 key={c} className={n === 1 ? "text-center" : n === 2 ? "text-right" : undefined}>{c}</h3>)}
      </div>
      {flow.claims.length === 0 && (
        <EmptyState icon={<NetworkIcon />} title="No claims in this answer"
          description="No study was determined and the answer lists nothing to draw; the papers and the verdict are still shown." />
      )}
      {/* role="group", not "img": an image role would hide the zoom controls and nodes from screen readers */}
      <div className="h-[60vh] rounded-md border" role="group" aria-label="Evidence graph">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodeClick={onNodeClick} fitView minZoom={0.1} nodesDraggable={false}
          colorMode={resolvedTheme === "dark" ? "dark" : "light"} proOptions={{ hideAttribution: true }}>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <details>
        <summary className="cursor-pointer text-sm">Nodes and edges as lists</summary>
        <div className="mt-2 grid gap-4 text-xs lg:grid-cols-2">
          <ul className="space-y-0.5" aria-label="Nodes">
            {flow.nodes.map((n) => (
              <li key={n.id}>
                <span className="text-muted-foreground">{n.data.column}:</span>{" "}
                {n.data.claim ? (
                  <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => setOpen(n.data.claim ?? null)}>{n.data.label}</Button>
                ) : n.data.column === "paper" ? (
                  <Link to={itemHref(n.data.label)} className="underline underline-offset-2">{n.data.label}</Link>
                ) : (
                  <>{n.data.label} <span className="text-muted-foreground">({n.data.rule})</span></>
                )}
              </li>
            ))}
          </ul>
          <ul className="space-y-0.5" aria-label="Edges">
            {flow.edges.map((e) => <li key={e.id}>{name(e.source)} —{String(e.label)}→ {name(e.target)}</li>)}
          </ul>
        </div>
      </details>
      <ClaimSheet graph={graph} claim={open} itemHref={itemHref} onClose={() => setOpen(null)} />
    </div>
  )
}
