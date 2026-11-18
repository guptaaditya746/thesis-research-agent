/** Box 3: the protocol. The planner's clarifying questions if it asked any, the lines, the decisions (confirm,
 * change, confirm all) and the problems; "Run on <domain> s<seed>" is enabled only when the plan is ready.
 * Done when the run starts. */
import { Button } from "@/components/ui/button"

import { confirmAll, decide, deleteLine, sendAnswers, startRun, useAction, type PlanView } from "../plan/api"
import { DecisionsPanel } from "../plan/DecisionsPanel"
import { LineCard } from "../plan/LineCard"
import { Clarify } from "../plan/PlanPage"
import { Box } from "./PickBox"

export function ProtocolBox({ view, domain, seed, onView, onError }: {
  view: PlanView | null
  domain: string | null
  seed: number | null
  onView: (view: PlanView) => void
  onError: (message: string | null) => void
}) {
  const take = (v: PlanView) => { onError(null); onView(v) }
  const fail = (e: unknown) => onError(e instanceof Error ? e.message : String(e))
  const id = view?.id ?? ""
  const answers = useAction((a: { question: string; answer: string }[]) => sendAnswers(id, a), take, fail)
  const confirm = useAction((did: string) => decide(id, did, { confirm: true }), take, fail)
  const change = useAction((a: { id: string; value: unknown }) => decide(id, a.id, { change: a.value }), take, fail)
  const all = useAction(() => confirmAll(id), take, fail)
  const remove = useAction((lid: string) => deleteLine(id, lid), take, fail)
  const run = useAction(() => startRun(id, { domain: domain ?? "", seed: seed ?? 0 }), (r) => { onError(null); if (view) onView({ ...view, frozen: true, run: r.run }) }, fail)
  const busy = [answers, confirm, change, all, remove, run].some((m) => m.isPending)
  const plan = view?.plan ?? null

  return (
    <Box title="3. Protocol" open={view !== null}>
      {view && !plan && <Clarify view={view} busy={busy} onSend={(a) => answers.mutate(a)} />}
      {view && plan && (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-3">
            <p className="text-sm font-medium">{`Answer kind: ${plan.answer_by ?? "lines"}`}</p>
            {plan.lines.map((l) => (
              <LineCard key={l.id} line={l} how={view.how[l.id]} busy={busy || view.frozen} onRemove={view.frozen ? undefined : (lid) => remove.mutate(lid)} />
            ))}
            <Button disabled={busy || view.frozen || !view.ready} onClick={() => run.mutate(undefined)}>{`Run on ${domain} s${seed}`}</Button>
            {view.run && <p className="text-sm text-muted-foreground">Run started: {view.run}</p>}
            {view.problems.length > 0 && (
              <ul role="alert" className="list-disc pl-5 text-sm text-destructive">{view.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            )}
            {!view.frozen && view.problems.length === 0 && !view.ready && <p className="text-xs text-muted-foreground">Confirm every decision to run.</p>}
          </div>
          <DecisionsPanel decisions={plan.decisions} busy={busy || view.frozen}
            onConfirm={(did) => confirm.mutate(did)} onChange={(did, value) => change.mutate({ id: did, value })} onConfirmAll={() => all.mutate(undefined)} />
        </div>
      )}
    </Box>
  )
}
