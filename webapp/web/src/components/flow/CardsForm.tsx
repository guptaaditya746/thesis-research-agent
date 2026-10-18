/**
 * The proposal's eight choice-point cards as a form (docs/evidence-system.md Part E): per card an option (or a
 * custom value in the card's shape, as JSON) and a reason, which is required. A card keeps the `by` it has in
 * decisions.yaml (the model's default, or whoever edited it by hand) until the user touches it; then it is the
 * app's user ($WEBAPP_USER). Save writes decisions.yaml (PUT, in the format evidence/propose/cards.py validates)
 * with the file's sha256 as the form loaded it: if the file changed since, the server refuses and the form offers
 * reload or overwrite. It shows what `evidence propose freeze` would refuse; Freeze starts that command as a job
 * once the saved decisions pass. Amendments after the freeze stay on the command line.
 */
import { LockIcon, SaveIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { isConflict } from "@/api/client"
import { useEvConfig, usePutDecisions, useStartJob, type Card as CardT, type ProposalDetail } from "@/api/ev"
import { JsonBlock } from "@/components/ev/bits"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { announceError, announceJob } from "@/lib/toasts"

import { CUSTOM, initialState, optionValue, toEntry, type CardState } from "./cards"


function CardField({ card, state, onChange, user }: { card: CardT; state: CardState; onChange: (s: CardState) => void; user: string }) {
  const touch = (patch: Partial<CardState>) => onChange({ ...state, ...patch, by: user })
  const { error } = toEntry(card, state)
  const id = `card-${card.id}`
  const shown = state.choice === CUSTOM ? null : optionValue(card, state.choice)
  return (
    <Card size="sm" role="group" aria-labelledby={`${id}-title`}>
      <CardHeader>
        <CardTitle id={`${id}-title`} className="flex flex-wrap items-center gap-2 text-sm">
          {card.title ?? card.id}
          <Badge variant={state.by === "model" ? "outline" : "secondary"}>{state.by === "model" ? "model's default" : `decided by ${state.by}`}</Badge>
          {state.choice !== card.default && <Badge>changed from the default</Badge>}
        </CardTitle>
        <CardDescription>{card.ask}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Model's default <span className="font-mono">{card.default}</span>{card.rationale ? `: ${card.rationale}` : ""}
        </p>
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-choice`}>Choice</Label>
          <Select value={state.choice} onValueChange={(choice) => touch({ choice })}>
            <SelectTrigger id={`${id}-choice`} aria-label={`Choice for ${card.id}`} className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {card.options.map((o) => (
                <SelectItem key={String(o.id)} value={String(o.id)}>{String(o.id)}: {String(o.summary ?? "")}</SelectItem>
              ))}
              <SelectItem value={CUSTOM}>custom: a value of my own (JSON)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {state.choice === CUSTOM ? (
          <div className="grid gap-1.5">
            <Label htmlFor={`${id}-value`}>Custom value (JSON in the card's shape)</Label>
            <Textarea id={`${id}-value`} className="min-h-28 font-mono text-xs" value={state.custom} onChange={(e) => touch({ custom: e.target.value })} />
          </div>
        ) : (
          <details>
            <summary className="cursor-pointer text-xs text-muted-foreground">value of {state.choice}</summary>
            <JsonBlock value={shown} className="mt-1 max-h-40" />
          </details>
        )}
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-reason`}>Reason (required)</Label>
          <Textarea id={`${id}-reason`} className="min-h-16" value={state.reason} onChange={(e) => touch({ reason: e.target.value })} aria-invalid={!!error} />
        </div>
        {error && <p className="text-xs text-destructive" role="alert">{card.id}: {error}</p>}
        {card.problems.length > 0 && (
          <ul className="space-y-0.5 text-xs text-destructive" aria-label={`Problems of ${card.id}`}>
            {card.problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

/** `onReload`: load decisions.yaml again and start the form from it (the parent remounts the form). */
export function CardsForm({ proposal, onReload }: { proposal: ProposalDetail; onReload: () => void }) {
  const config = useEvConfig()
  const user = config.data?.user
  const navigate = useNavigate()
  const [states, setStates] = useState<Record<string, CardState>>(() =>
    Object.fromEntries(proposal.cards.map((c) => [c.id, initialState(c)])))
  const [dirty, setDirty] = useState(false)
  const [base, setBase] = useState(proposal.decisions_sha256)   // the file as this form loaded it
  const [stale, setStale] = useState(false)
  const save = usePutDecisions(proposal.name)
  const freeze = useStartJob("freeze")
  const entries = proposal.cards.map((c) => ({ card: c, ...toEntry(c, states[c.id]) }))
  const errors = entries.filter((e) => e.error)
  const problems = save.data?.problems ?? proposal.decision_problems

  const onSave = (force = false) =>
    save.mutate({ decisions: entries.map((e) => e.entry), base_sha256: base, force }, {
      onSuccess: (result) => { setDirty(false); setStale(false); setBase(result.sha256) },
      onError: (e) => (isConflict(e) ? setStale(true) : announceError("Saving the decisions failed", e)),
    })
  const onFreeze = () =>
    freeze.mutate({ proposal: proposal.name }, {
      onSuccess: (job) => announceJob(job, navigate),
      onError: (e) => announceError(isConflict(e) ? "Freeze refused" : "Freeze failed", e),
    })

  return (
    <section className="space-y-4" aria-label="Cards">
      <div className="grid gap-4 xl:grid-cols-2">
        {proposal.cards.map((c) => (
          <CardField key={c.id} card={c} state={states[c.id]} user={user ?? "you"}
            onChange={(s) => { setStates((old) => ({ ...old, [c.id]: s })); setDirty(true) }} />
        ))}
      </div>
      {stale && (
        <div role="alert" className="space-y-2 rounded-md border border-status-warning/60 bg-status-warning/10 p-3 text-sm">
          <p className="font-medium">decisions.yaml changed since this form loaded it (a hand edit, or another tab).</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={onReload}>Reload it (drops your unsaved changes)</Button>
            <Button size="sm" variant="destructive" onClick={() => onSave(true)} disabled={save.isPending}>Overwrite it with this form</Button>
          </div>
        </div>
      )}
      {problems.length > 0 && !dirty && (
        <div role="status" className="rounded-md border border-destructive/50 p-3 text-sm">
          <p className="font-medium">decisions.yaml: freeze would refuse it</p>
          <ul className="mt-1 list-disc pl-5 text-xs">{problems.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => onSave()} disabled={errors.length > 0 || save.isPending || !user}>
          <SaveIcon data-icon="inline-start" />
          Save decisions
        </Button>
        <Button variant="outline" onClick={onFreeze} disabled={dirty || problems.length > 0 || !proposal.steps.includes("cards") || freeze.isPending}>
          <LockIcon data-icon="inline-start" />
          Freeze
        </Button>
        <span className="text-xs text-muted-foreground">
          {errors.length > 0 ? `${errors.length} card(s) need a reason or valid JSON.` : dirty ? "Unsaved changes: save before freezing." : save.isSuccess ? "Saved." : ""}
          {" "}Freeze writes protocol.yaml (revision 1); after that, changes go through <span className="font-mono">evidence propose amend</span> on the command line.
        </span>
      </div>
    </section>
  )
}
