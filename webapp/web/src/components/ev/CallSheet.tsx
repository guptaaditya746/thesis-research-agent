/**
 * One extractor call, opened from a paper's call list: its checked result (status, items, rejected
 * proposals with the reason, coverage), the task (scope, context, the funnel's focus), and what made it:
 * for an LLM extractor the model calls from the record cache (instructions, user prompt, the decoded
 * output, usage), for the agentic extractor the agent run's trace.
 */
import { useState } from "react"

import { useCall, useCallTrace } from "@/api/ev"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { itemLabel, typeLabel } from "@/lib/ev"
import { tokens } from "@/lib/format"

import { AgentTraceView } from "./AgentTraceView"
import { Capped, JsonBlock, KeyValues } from "./bits"

function Trace({ runId, callId, agentRun }: { runId: string; callId: string; agentRun: string }) {
  const trace = useCallTrace(runId, callId, agentRun)
  if (trace.isPending) return <CardsSkeleton count={1} />
  if (trace.isError) return <ErrorState error={trace.error} title="Could not load the agent's trace" onRetry={() => void trace.refetch()} />
  return <AgentTraceView trace={trace.data} />
}

function CallBody({ runId, callId }: { runId: string; callId: string }) {
  const call = useCall(runId, callId)
  const [agentRun, setAgentRun] = useState<string | null>(null)
  if (call.isPending) return <CardsSkeleton count={2} className="md:grid-cols-1 xl:grid-cols-1" />
  if (call.isError) return <ErrorState error={call.error} onRetry={() => void call.refetch()} />
  const { call: c, result, task, model_calls: records, agent_runs: agentRuns } = call.data
  const shown = agentRun ?? (agentRuns.length === 1 ? agentRuns[0] : null)
  return (
    <div className="space-y-5">
      <KeyValues items={[
        ["extractor", <span key="e" className="font-mono text-xs break-all">{c.extractor_id}</span>],
        ["kind", c.kind ?? "—"],
        ["evidence type", typeLabel(c.evidence_type)],
        ["paper", c.document],
        ["position", c.position === null || c.position === undefined ? "—" : `${c.position} in the cascade`],
        ["status", <Badge key="s" variant={result.status === "ok" ? "secondary" : "destructive"}>{result.status}</Badge>],
        ["from", `${c.source ?? "—"}${c.attempt ? `, attempt ${c.attempt}` : ""}`],
        ["focus", c.focus ? <span key="f" className="font-mono">{c.focus}</span> : "untargeted"],
      ]} />
      {result.error && <JsonBlock value={result.error} label="error" />}
      <section className="space-y-2">
        <h3 className="text-sm font-medium">Items ({result.items?.length ?? 0})</h3>
        <Capped items={result.items ?? []}>{(items) => (
        <ul className="space-y-1 text-sm">
          {items.map((i) => (
            <li key={i.item_id} className="rounded border p-2">
              <span className="font-mono text-xs text-muted-foreground">{i.item_id}</span> {itemLabel(i)}
              <span className="block text-xs text-muted-foreground">
                {i.spans.map((s) => `${s.role}: “${String((s.selector as Record<string, unknown>).exact ?? "")}”`).join(" · ")}
              </span>
            </li>
          ))}
        </ul>
        )}</Capped>
        {(result.rejected ?? []).length > 0 && (
          <>
            <h3 className="text-sm font-medium">Rejected by the engine's checks ({result.rejected!.length})</h3>
            <Capped items={result.rejected!}>{(rejected) => (
            <ul className="space-y-1 text-xs">
              {rejected.map((r, i) => (
                <li key={i} className="rounded border border-destructive/40 p-2">
                  <Badge variant="destructive" className="mr-1">{r.reason}</Badge>
                  {r.detail} {(r.quotes ?? []).map((q) => <q key={q} className="ml-1">{q}</q>)}
                </li>
              ))}
            </ul>
            )}</Capped>
          </>
        )}
        {(result.coverage ?? []).length > 0 && (
          <p className="text-xs text-muted-foreground">
            Coverage: {result.coverage!.map((v) => `${v.range ? `${v.range[0]}–${v.range[1]}` : v.section ?? "?"} ${v.status}${v.reason ? ` (${v.reason})` : ""}`).join("; ")}
          </p>
        )}
      </section>
      {task && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">Task</summary>
          <JsonBlock value={task} className="mt-1" />
        </details>
      )}
      {call.data.record_note ? (
        <p className="text-xs text-muted-foreground">{call.data.record_note[0].toUpperCase() + call.data.record_note.slice(1)}.</p>
      ) : !call.data.cached && c.kind !== "regex" && (
        <p className="text-xs text-muted-foreground">The record cache ($EV_CACHE) does not hold this call: its model calls cannot be shown.</p>
      )}
      {records.length > 0 && !agentRuns.length && (
        <section className="space-y-3">
          <h3 className="text-sm font-medium">Model calls ({records.length})</h3>
          {records.map((m) => {
            const request = (m.request ?? {}) as Record<string, unknown>
            const usage = (m.usage ?? {}) as Record<string, number | undefined>
            return (
              <div key={m.id} className="space-y-2 rounded-md border p-3">
                <p className="text-xs text-muted-foreground">
                  <span className="font-mono">{m.id}</span> · {String(request.model ?? "")} · {tokens(usage.input_tokens ?? null)} in, {tokens(usage.output_tokens ?? null)} out
                </p>
                {m.error && <p className="text-xs text-destructive">{m.error}</p>}
                <details>
                  <summary className="cursor-pointer text-xs">instructions</summary>
                  <JsonBlock value={String(request.instructions ?? "")} className="mt-1" />
                </details>
                <details>
                  <summary className="cursor-pointer text-xs">user prompt</summary>
                  <JsonBlock value={String(request.user_prompt ?? "")} className="mt-1" />
                </details>
                <JsonBlock value={(m.response as Record<string, unknown> | null)?.output ?? m.response ?? null} label="model output" />
              </div>
            )
          })}
        </section>
      )}
      {agentRuns.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-medium">Agent run{agentRuns.length > 1 ? "s" : ""}</h3>
          {agentRuns.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {agentRuns.map((a) => (
                <Button key={a} size="sm" variant={a === shown ? "default" : "outline"} aria-pressed={a === shown} onClick={() => setAgentRun(a)} className="font-mono">{a}</Button>
              ))}
            </div>
          )}
          {shown && <Trace runId={runId} callId={callId} agentRun={shown} />}
        </section>
      )}
    </div>
  )
}

export function CallSheet({ runId, callId, onClose }: { runId: string; callId: string | null; onClose: () => void }) {
  return (
    <Sheet open={!!callId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>Call {callId}</SheetTitle>
          <SheetDescription>What the extractor returned, what the engine kept, and what made it.</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">{callId && <CallBody runId={runId} callId={callId} />}</div>
      </SheetContent>
    </Sheet>
  )
}

