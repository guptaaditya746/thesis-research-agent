/**
 * The kind of the question (effect, inventory, consistency, best): the frame step's guess is shown, and the
 * person confirms it or changes it. A change (PUT /proposals/{name}/kind) drafts the protocol, the critic and the
 * cards again from that kind's template, so the cards and decisions made so far are dropped.
 */
import { useState } from "react"
import { useNavigate } from "react-router"

import { usePutKind, useEvConfig, type ProposalDetail, type QuestionKind } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { announceError, announceJob } from "@/lib/toasts"

const KINDS: { id: QuestionKind; what: string }[] = [
  { id: "effect", what: "does a treatment change an outcome, and in which direction" },
  { id: "inventory", what: "list every metric, method or dataset the papers use" },
  { id: "consistency", what: "do the claims of the papers agree with their results" },
  { id: "best", what: "which kind of method does best, paper by paper" },
]

export function KindConfirm({ proposal }: { proposal: ProposalDetail }) {
  const frame = proposal.frame ?? {}
  const kind = (KINDS.some((k) => k.id === frame.kind) ? frame.kind : "effect") as QuestionKind
  const byUser = frame.kind_by === "user"
  const article = /^[aeiou]/.test(kind) ? "an" : "a"
  const [chosen, setChosen] = useState<QuestionKind | null>(null)
  const config = useEvConfig()
  const put = usePutKind(proposal.name)
  const navigate = useNavigate()
  const next = chosen ?? kind
  const frozen = proposal.frozen
  return (
    <section aria-label="Kind of question" className="space-y-2 rounded-lg border p-3">
      <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">Kind of question <Badge>{kind}</Badge></h3>
      <p className="text-sm text-muted-foreground">
        {byUser ? `You said this is ${article} ${kind} question.` : `The model reads this as ${article} ${kind} question.`}{" "}
        {KINDS.find((k) => k.id === kind)?.what}. Each kind has its own cards.
      </p>
      {!frozen && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="grid w-full gap-1 sm:w-auto">
            <Label htmlFor="kind-choice" className="text-xs">Kind</Label>
            <Select value={next} onValueChange={(k) => setChosen(k as QuestionKind)}>
              <SelectTrigger id="kind-choice" aria-label="Kind" className="w-full sm:w-80"><SelectValue /></SelectTrigger>
              <SelectContent>{KINDS.map((k) => <SelectItem key={k.id} value={k.id}>{k.id}: {k.what}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button size="sm" variant="outline" disabled={next === kind || put.isPending}
            onClick={() => put.mutate({ kind: next, model: config.data?.default_model ?? "orch-model" }, {
              onSuccess: (job) => { setChosen(null); announceJob(job, navigate) },
              onError: (e) => announceError("The kind was not changed", e),
            })}>
            Use this kind
          </Button>
          <p className="w-full text-xs text-muted-foreground">Changing the kind drafts the protocol and the cards again; the decisions made so far are dropped.</p>
        </div>
      )}
    </section>
  )
}
