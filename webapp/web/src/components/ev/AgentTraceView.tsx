/**
 * The research agent's trace behind an agentic call or the agent baseline: per step its model call, the
 * command and the head of its output, the claims it sent with their verdict; then every claim and the
 * agent's answer. From the agent's own run directory (events.jsonl, claims.jsonl) or, when that is not
 * kept, from the record the engine's cache holds (commands, claims, model calls; no replies).
 */
import { CheckCircle2Icon, OctagonXIcon } from "lucide-react"

import type { AgentTrace } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { Badge } from "@/components/ui/badge"
import { tokens } from "@/lib/format"

import { JsonBlock, KeyValues } from "./bits"

export function AgentTraceView({ trace }: { trace: AgentTrace }) {
  const outcome = (trace.outcome ?? {}) as Record<string, unknown>
  return (
    <div className="space-y-4">
      <KeyValues items={[
        ["agent run", <span key="r" className="font-mono text-xs">{trace.run_id}</span>],
        ["from", trace.source === "run_dir" ? "the agent's run directory" : "the engine's record cache (the run directory is not kept)"],
        ["exit", String(outcome.exit_status ?? "—")],
        ["steps", String(trace.steps.length)],
        ["claims", `${trace.claims.filter((c) => c.status === "accepted").length} accepted, ${trace.claims.filter((c) => c.status === "rejected").length} rejected`],
      ]} />
      <ol className="space-y-3" aria-label="Steps">
        {trace.steps.map((s) => (
          <li key={`${s.agent_id}-${s.step}`} className="rounded-md border p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">step {s.step}</span>
              {s.agent_id !== "main" && <Badge variant="outline" className="font-mono">{s.agent_id}</Badge>}
              {s.phase && <Badge variant="secondary">{s.phase}</Badge>}
              {s.model_call && (
                <span className="text-xs text-muted-foreground">
                  model call {s.model_call.reply ? `(${s.model_call.reply})` : ""} · {tokens(s.model_call.tokens ?? null)} tokens
                </span>
              )}
              {(s.coverage ?? []).map((c) => <Badge key={c} variant="outline">{c}</Badge>)}
            </div>
            {s.command && (
              <div className="mt-2 space-y-1">
                <pre className="overflow-auto rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">$ {s.command}</pre>
                {s.output_head && (
                  <details>
                    <summary className="cursor-pointer text-xs text-muted-foreground">output (exit {s.exit_code ?? "?"})</summary>
                    <pre className="mt-1 max-h-60 overflow-auto rounded border p-2 font-mono text-xs whitespace-pre-wrap">{s.output_head}</pre>
                  </details>
                )}
              </div>
            )}
            {(s.claims ?? []).length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-2">
                {(s.claims ?? []).map((c, i) => (
                  <li key={i}>
                    <StatusBadge tone={c.status === "accepted" ? "good" : "critical"} icon={c.status === "accepted" ? <CheckCircle2Icon /> : <OctagonXIcon />}
                      title={`${String(c.s)} | ${String(c.p)} | ${String(c.o)}`}>
                      claim {c.status}{c.reason ? `: ${c.reason}` : ""}
                    </StatusBadge>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
      {trace.claims.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium">Claims</h3>
          <ul className="space-y-1 text-xs">
            {trace.claims.map((c, i) => (
              <li key={i} className="rounded border p-2">
                <span className="font-mono">{c.claim_id ?? "rejected"}</span> · {c.paper_id ?? c.file ?? "?"} · {c.status}
                {c.reason ? ` (${c.reason})` : ""}: <q>{c.quote}</q>
              </li>
            ))}
          </ul>
        </div>
      )}
      {trace.answer && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">The agent's answer</summary>
          <JsonBlock value={trace.answer} className="mt-1" />
        </details>
      )}
    </div>
  )
}
