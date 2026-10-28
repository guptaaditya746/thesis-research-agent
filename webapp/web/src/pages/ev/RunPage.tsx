/**
 * Run `/runs/:runId` (`<group>~<name>`): what the run is (system, selection, strategy, model, protocol,
 * corpus, cost) and tabs for the answer (the evidence table: the answer, a row per paper by verdict, one click
 * to the sentence; a baseline's text, citations and retrieved passages), the papers (each with where the
 * funnel stopped, opening the paper view), the protocol it ran, its extractors, the agent baseline's trace,
 * and for an engine run the Developer tools tab: its step trace (live) and the raw evidence graph
 * (graph.json in React Flow, and as JSON). The baselines on the same corpus and the run's score reports are
 * linked. The tab is in the URL (?tab=, and ?dev= inside Developer tools; the old ?tab=graph opens the
 * graph there). While a job of the app writes the run, the page polls, so an incomplete run fills in as the
 * engine writes it.
 */
import type { ReactNode } from "react"
import { Link, useParams, useSearchParams } from "react-router"

import { useActiveJobs, useBaselineTrace, useCorpus, useEvRun, useRunGraph, useRunProtocol, type EvRunDetail } from "@/api/ev"
import { AgentTraceView } from "@/components/ev/AgentTraceView"
import { ErrorCallsBadge } from "@/components/badges"
import { JsonBlock, KeyValues, QueryPage, RowsTable, SystemBadge } from "@/components/ev/bits"
import { TraceTab } from "@/components/ev/TraceTab"
import { EvidenceGraph } from "@/components/ev/EvidenceGraph"
import { EvidenceView } from "@/components/ev/EvidenceView"
import { ProtocolPanel } from "@/components/ev/ProtocolPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { effectAnswer, funnelStop } from "@/lib/ev"
import { duration, tokens } from "@/lib/format"

const runHref = (id: string) => `/runs/${encodeURIComponent(id)}`

function GraphTab({ run }: { run: EvRunDetail }) {
  const graph = useRunGraph(run.id)
  if (graph.isPending) return <CardsSkeleton count={1} />
  if (graph.isError) return <ErrorState error={graph.error} />
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        The engine's raw evidence graph (graph.json): every item and link, for debugging. The Answer tab shows the same
        evidence as a row per paper.
      </p>
      <EvidenceGraph graph={graph.data} documents={run.documents} paperHref={(d) => `${runHref(run.id)}/papers/${encodeURIComponent(d)}`} />
      <details>
        <summary className="cursor-pointer text-sm">graph.json</summary>
        <JsonBlock value={graph.data} label="graph.json" className="mt-2" />
      </details>
    </div>
  )
}

const DEV_TABS = [{ value: "trace", label: "Step trace" }, { value: "graph", label: "Evidence graph" }]

/** Developer tools: the run's step trace and its raw evidence graph, each behind its own tab (?dev=). */
function DevTools({ run, sub, onSub }: { run: EvRunDetail; sub: string; onSub: (v: string) => void }) {
  return (
    <Tabs value={sub} onValueChange={onSub} className="space-y-3">
      <TabsList aria-label="Developer tools">
        {DEV_TABS.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
      </TabsList>
      <TabsContent value="trace">{sub === "trace" && <TraceTab runId={run.id} />}</TabsContent>
      <TabsContent value="graph">{sub === "graph" && <GraphTab run={run} />}</TabsContent>
    </Tabs>
  )
}

function ProtocolTab({ runId }: { runId: string }) {
  const protocol = useRunProtocol(runId)
  if (protocol.isPending) return <CardsSkeleton count={1} />
  if (protocol.isError) return <ErrorState error={protocol.error} />
  return <ProtocolPanel view={protocol.data} />
}

function AgentTraceTab({ runId }: { runId: string }) {
  const trace = useBaselineTrace(runId)
  if (trace.isPending) return <CardsSkeleton count={1} />
  if (trace.isError) return <ErrorState error={trace.error} />
  return <AgentTraceView trace={trace.data} />
}

function PapersTab({ run }: { run: EvRunDetail }) {
  const studies = new Map((effectAnswer(run.answer)?.studies ?? []).map((s) => [s.document, s]))
  return (
    <div className="overflow-auto rounded-md border">
      <Table aria-label="Papers">
        <TableHeader>
          <TableRow>
            {["paper", "screen", "steps run", "funnel", "direction"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {run.documents.map((d) => {
            const f = run.funnel?.[d]
            const screen = (f?.screen ?? null) as { relevant?: boolean; reason?: string } | null
            return (
              <TableRow key={d}>
                <TableCell className="font-mono text-xs"><Link to={`${runHref(run.id)}/papers/${encodeURIComponent(d)}`} className="hover:underline">{d}</Link></TableCell>
                <TableCell className="text-xs" title={screen?.reason}>{screen ? (screen.relevant ? "relevant" : "not relevant") : "—"}</TableCell>
                <TableCell className="text-xs tabular-nums">{f ? f.steps?.map((s) => `r${s.round}·p${s.position}`).join(", ") : "—"}</TableCell>
                <TableCell className="text-xs">{funnelStop(f, run.strategy)}</TableCell>
                <TableCell className="text-xs">{studies.get(d)?.direction ?? "—"}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

function RunView({ run }: { run: EvRunDetail }) {
  const [params, setParams] = useSearchParams()
  const corpus = useCorpus(run.corpus ?? "")
  const engine = run.kind === "engine"
  const tabs = [
    { value: "answer", label: "Answer" },
    { value: "papers", label: "Papers" },
    ...(engine ? [{ value: "protocol", label: "Protocol" }, { value: "extractors", label: "Extractors" }, { value: "dev", label: "Developer tools" }] : []),
    ...(run.has_trace ? [{ value: "trace", label: "Agent trace" }] : []),
  ]
  // ?tab=graph (before the graph moved under Developer tools) still opens it
  const asked = params.get("tab") === "graph" ? "dev" : params.get("tab")
  const tab = tabs.some((t) => t.value === asked) ? asked! : "answer"
  const dev = params.get("tab") === "graph" ? "graph" : DEV_TABS.some((t) => t.value === params.get("dev")) ? params.get("dev")! : "trace"
  const cost = (run.cost ?? {}) as Record<string, number | undefined>
  return (
    <div className="space-y-6">
      <PageHeader title={<span className="font-mono">{run.group} / {run.name}</span>} description={run.corpus ? <>on <Link to={`/corpora/${encodeURIComponent(run.corpus)}`} className="font-mono underline">{run.corpus}</Link></> : run.corpus_id}>
        <div className="flex flex-wrap items-center gap-2">
          <SystemBadge system={run.system} />
          {run.selection && <Badge variant="outline">{run.selection}</Badge>}
          {run.strategy && <Badge variant="outline">strategy {run.strategy}</Badge>}
          {run.mode && run.mode !== "run" && <Badge variant="secondary">{run.mode}</Badge>}
          {!run.complete && <Badge variant="destructive">incomplete: no run.json (crashed or still running); events and calls only</Badge>}
          <ErrorCallsBadge count={run.error_calls} />
        </div>
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Run</CardTitle></CardHeader>
          <CardContent>
            <KeyValues items={[
              ["model", run.model ?? "—"],
              ["protocol", run.protocol ? <span key="p" className="font-mono text-xs">{String(run.protocol.id)} · {String(run.protocol.sha256 ?? "").slice(0, 12)}</span> : "none (a baseline reads the question only)"],
              ["papers", String(run.documents.length)],
              ["cost", engine ? `${cost.calls ?? 0} calls (${cost.cached_calls ?? 0} from the cache), ${cost.model_calls ?? 0} model calls, ${tokens((cost.input_tokens ?? 0) + (cost.output_tokens ?? 0))} tokens, ${duration(cost.seconds ?? null)}` : "—"],
              ...(run.chain_head ? [["chain head", <span key="h" className="font-mono text-xs">{run.chain_head.slice(0, 16)}</span>] as [string, ReactNode]] : []),
              ...(run.source_run ? [["source run", run.source_run] as [string, string]] : []),
            ]} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Beside it</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>Baselines on this corpus: {run.baselines.length ? run.baselines.map((b) => <Link key={b} to={runHref(b)} className="mr-2 font-mono text-xs underline">{b}</Link>) : "none"}</div>
            <div>Score reports: {run.reports.length ? run.reports.map((r) => <Link key={r} to={`/scores/reports/${encodeURIComponent(r)}`} className="mr-2 font-mono text-xs underline">{r}</Link>) : "none"}</div>
          </CardContent>
        </Card>
      </div>
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })}>
        <TabsList className="h-auto max-w-full flex-wrap justify-start group-data-horizontal/tabs:h-auto">{tabs.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}</TabsList>
        <TabsContent value="answer" className="space-y-4">
          <EvidenceView run={run} expected={effectAnswer(run.answer) ? corpus.data?.answer?.label : null} />
        </TabsContent>
        <TabsContent value="papers"><PapersTab run={run} /></TabsContent>
        {engine && <TabsContent value="protocol">{tab === "protocol" && <ProtocolTab runId={run.id} />}</TabsContent>}
        {engine && (
          <TabsContent value="extractors">
            <RowsTable caption="Extractors" rows={run.extractors as unknown as Record<string, unknown>[]} columns={["name", "version", "kind", "evidence_types", "determinism", "code_sha256"]}
              render={(c, v) => (c === "code_sha256" ? <span className="font-mono">{String(v).slice(0, 12)}</span> : Array.isArray(v) ? v.join(", ") : String(v ?? "—"))} />
          </TabsContent>
        )}
        {engine && (
          <TabsContent value="dev">
            {tab === "dev" && <DevTools run={run} sub={dev} onSub={(v) => setParams({ tab: "dev", dev: v }, { replace: true })} />}
          </TabsContent>
        )}
        {run.has_trace && <TabsContent value="trace">{tab === "trace" && <AgentTraceTab runId={run.id} />}</TabsContent>}
      </Tabs>
    </div>
  )
}

export default function RunPage() {
  const { runId = "" } = useParams()
  const live = useActiveJobs({ run: runId }).length > 0   // a job of the app writes it: poll until it ends
  const run = useEvRun(runId, live)
  return (
    <QueryPage query={run} what={`run ${runId}`} back={{ to: "/runs", label: "All runs" }}>
      {(data) => <RunView run={data} />}
    </QueryPage>
  )
}
