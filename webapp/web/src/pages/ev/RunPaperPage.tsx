/**
 * A paper in a run `/runs/:runId/papers/:doc`: the funnel on it (the screen's decision and reason, each
 * round's position and evidence types with their calls, the completeness decisions and gaps, where it
 * stopped), the paper's text with the spans of every merged item marked by evidence type (a baseline's
 * cited passages instead), the items with the extractors that found them (`found_by`), the study's line of
 * the answer, and every call; a call opens its sheet (model records, the agent's trace). The paper's
 * neighbours are a click away.
 */
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useParams } from "react-router"

import { useEvRun, useRunPaper, type CallSummary, type RunPaper } from "@/api/ev"
import { CallSheet } from "@/components/ev/CallSheet"
import { DirectionBadge, KeyValues, QueryPage } from "@/components/ev/bits"
import { MarkLegend, PaperText } from "@/components/ev/PaperText"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { EVIDENCE_TYPES, extractorName, funnelStop, itemLabel, TYPE_COLOR, typeLabel } from "@/lib/ev"
import { num } from "@/lib/format"

const CITED = "var(--chart-2)"

function CallButton({ call, onOpen }: { call: CallSummary; onOpen: (id: string) => void }) {
  return (
    <Button size="sm" variant="outline" className="h-6 px-2 font-mono text-xs" onClick={() => onOpen(call.call_id)}
      title={`${call.extractor_id}: ${call.status}, ${call.items} item(s)${call.focus ? `, focus ${call.focus}` : ""}`}>
      {extractorName(call.extractor_id)}
    </Button>
  )
}

function Funnel({ paper, strategy, calls, onOpen }: { paper: RunPaper; strategy?: string | null; calls: Map<string, CallSummary>; onOpen: (id: string) => void }) {
  const f = paper.funnel
  if (!f) return null
  const screen = (f.screen ?? null) as { relevant?: boolean; reason?: string; calls?: string[]; extractor?: string } | null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Funnel</CardTitle>
        <CardDescription>{funnelStop(f, strategy)}{strategy ? ` (strategy ${strategy})` : ""}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {screen && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">screen</span>
            <Badge variant={screen.relevant ? "secondary" : "destructive"}>{screen.relevant ? "relevant" : "not relevant"}</Badge>
            <span>{screen.reason}</span>
            {(screen.calls ?? []).map((id) => calls.get(id) && <CallButton key={id} call={calls.get(id)!} onOpen={onOpen} />)}
          </div>
        )}
        <ol className="space-y-2">
          {(f.steps ?? []).map((s, i) => {
            const decision = (f.decisions ?? []).find((d) => d.after_round === s.round && i === (f.steps ?? []).findLastIndex((x) => x.round === s.round))
            return (
              <li key={i} className="rounded border p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="font-mono">round {s.round} · position {s.position}</Badge>
                  <span className="text-xs text-muted-foreground">{s.types.map(typeLabel).join(", ")}</span>
                  {s.calls.map((id) => calls.get(id) && <CallButton key={id} call={calls.get(id)!} onOpen={onOpen} />)}
                </div>
                {decision && (
                  <p className="mt-1 text-xs">
                    {decision.complete ? "complete" : <>incomplete: gap <span className="font-mono">{decision.gap}</span> → escalate {decision.gap_types?.map(typeLabel).join(", ") || "nothing"}</>}
                  </p>
                )}
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}

function PaperView({ runId, paper, documents, strategy }: { runId: string; paper: RunPaper; documents: string[]; strategy?: string | null }) {
  const [call, setCall] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const types = useMemo(() => new Map(paper.items.map((i) => [i.item_id, i.evidence_type])), [paper.items])
  const calls = useMemo(() => new Map(paper.calls.map((c) => [c.call_id, c])), [paper.calls])
  const at = documents.indexOf(paper.document)
  const href = (d: string) => `/runs/${encodeURIComponent(runId)}/papers/${encodeURIComponent(d)}`
  const study = paper.study
  return (
    <div className="space-y-6">
      <PageHeader title={<span className="font-mono">{paper.document}</span>}
        description={<Link to={`/runs/${encodeURIComponent(runId)}`} className="font-mono underline">{runId}</Link>}
        actions={
          <>
            <Button asChild size="sm" variant="outline" disabled={at <= 0}>
              {at > 0 ? <Link to={href(documents[at - 1])}><ChevronLeftIcon data-icon="inline-start" />{documents[at - 1]}</Link> : <span>first</span>}
            </Button>
            <Button asChild size="sm" variant="outline" disabled={at < 0 || at >= documents.length - 1}>
              {at >= 0 && at < documents.length - 1 ? <Link to={href(documents[at + 1])}>{documents[at + 1]}<ChevronRightIcon data-icon="inline-end" /></Link> : <span>last</span>}
            </Button>
          </>
        }>
        {study && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <DirectionBadge direction={study.direction} />
            {study.treatment && study.control && <span className="font-mono text-xs">{num(study.treatment.value ?? null, 3)} vs {num(study.control.value ?? null, 3)} on {study.metric}</span>}
            {study.reason && <span className="text-muted-foreground">{study.reason.text ?? study.reason.code}</span>}
          </div>
        )}
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-2">
          {paper.text === null || paper.text === undefined ? (
            <p className="text-sm text-muted-foreground">The run's corpus is not under the corpora root, so its text cannot be shown; the items and calls are below.</p>
          ) : (
            <>
              <MarkLegend entries={[...EVIDENCE_TYPES.map((t) => ({ label: typeLabel(t), color: TYPE_COLOR[t] })), ...(paper.segments.some((s) => s.marks?.some((m) => m.startsWith("cited:"))) ? [{ label: "cited passage", color: CITED }] : [])]} />
              <PaperText label={`Text of ${paper.document}`} segments={paper.segments} selected={selected}
                colorOf={(m) => (m.startsWith("cited:") ? CITED : TYPE_COLOR[types.get(m) ?? ""] ?? null)}
                onSelect={(marks) => setSelected(marks.find((m) => types.has(m)) ?? null)} />
            </>
          )}
        </div>
        <div className="space-y-4">
          <Funnel paper={paper} strategy={strategy} calls={calls} onOpen={setCall} />
          <Card>
            <CardHeader><CardTitle className="text-base">Items ({paper.items.length})</CardTitle><CardDescription>Merged over the cascade; click one to find its spans in the text.</CardDescription></CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {paper.items.map((i) => (
                  <li key={i.item_id}>
                    <button type="button" onClick={() => setSelected(i.item_id)} aria-pressed={selected === i.item_id}
                      className={`w-full rounded border p-2 text-left text-sm hover:bg-muted ${selected === i.item_id ? "border-foreground" : ""}`}>
                      <span className="mr-2 inline-block size-2 rounded-full" style={{ background: TYPE_COLOR[i.evidence_type] }} aria-hidden="true" />
                      <span className="text-xs text-muted-foreground">{typeLabel(i.evidence_type)}</span> {itemLabel(i)}
                      <span className="block text-xs text-muted-foreground">found by {(i.found_by ?? []).map(extractorName).join(", ") || "—"}{Object.keys(i.links ?? {}).length ? ` · links ${Object.keys(i.links ?? {}).join(", ")}` : ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          {study?.author_claim && (
            <KeyValues items={[["author claim", `${String(study.author_claim.direction)}${study.author_claim.agrees_with_data === false ? " (disagrees with the data)" : ""}`]]} />
          )}
        </div>
      </div>
      {paper.calls.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-base font-semibold">Calls ({paper.calls.length})</h2>
          <div className="overflow-auto rounded-md border">
            <Table aria-label="Calls">
              <TableHeader>
                <TableRow>{["call", "type", "extractor", "kind", "position", "status", "items", "rejected", "focus", "from"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}</TableRow>
              </TableHeader>
              <TableBody>
                {paper.calls.map((c) => (
                  <TableRow key={c.call_id}>
                    <TableCell><Button size="sm" variant="link" className="h-auto p-0 font-mono text-xs" onClick={() => setCall(c.call_id)}>{c.call_id}</Button></TableCell>
                    <TableCell className="text-xs">{typeLabel(c.evidence_type)}</TableCell>
                    <TableCell className="font-mono text-xs">{extractorName(c.extractor_id)}</TableCell>
                    <TableCell className="text-xs">{c.kind ?? "—"}</TableCell>
                    <TableCell className="text-xs tabular-nums">{c.position ?? "—"}</TableCell>
                    <TableCell className="text-xs">{c.status}</TableCell>
                    <TableCell className="text-xs tabular-nums">{c.items}</TableCell>
                    <TableCell className="text-xs tabular-nums">{c.rejected}</TableCell>
                    <TableCell className="font-mono text-xs">{c.focus ?? ""}</TableCell>
                    <TableCell className="text-xs">{c.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}
      <CallSheet runId={runId} callId={call} onClose={() => setCall(null)} />
    </div>
  )
}

export default function RunPaperPage() {
  const { runId = "", doc = "" } = useParams()
  const run = useEvRun(runId)
  const paper = useRunPaper(runId, doc)
  return (
    <QueryPage query={paper} what={`paper ${doc} in run ${runId}`} back={{ to: `/runs/${encodeURIComponent(runId)}`, label: "The run" }}>
      {(data) => <PaperView key={data.document} runId={runId} paper={data} documents={run.data?.documents ?? []} strategy={run.data?.strategy} />}
    </QueryPage>
  )
}
