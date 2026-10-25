/**
 * The proposal's eight choice-point cards as a form (docs/evidence-system.md Part E): per card an option (or a
 * custom value in the card's shape, as JSON) and a reason, which is required. A card keeps the `by` it has in
 * decisions.yaml (the model's default, or whoever edited it by hand) until the user touches it; then it is the
 * app's user ($WEBAPP_USER). Save writes decisions.yaml (PUT, in the format evidence/propose/cards.py validates)
 * with the file's sha256 as the form loaded it: if the file changed since, the server refuses and the form offers
 * reload or overwrite. It shows what `evidence propose freeze` would refuse; Freeze starts that command as a job
 * once the saved decisions pass. Amendments after the freeze stay on the command line.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { LockIcon, SaveIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { isConflict } from "@/api/client"
import { evApi, evKeys, useEvConfig, usePutDecisions, useStartJob, type Card as CardT, type ProposalDetail } from "@/api/ev"
import { JsonBlock } from "@/components/ev/bits"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useDebounced } from "@/hooks/use-debounced"
import { announceError, announceJob } from "@/lib/toasts"

import { CheckerPanel } from "./CheckerPanel"
import { CUSTOM, advancedCard, initialState, optionValue, toEntry, type CardState } from "./cards"
import { PaperPreview } from "./PaperPreview"
import { WaiverDialog } from "./WaiverDialog"

/** The checker waits for the typing to stop (the endpoint re-applies every decision to the draft). */
export const CHECK_DEBOUNCE_MS = 400


function CardField({ card, state, onChange, user }: { card: CardT; state: CardState; onChange: (s: CardState) => void; user: string }) {
  const touch = (patch: Partial<CardState>) => onChange({ ...state, ...patch, by: user })
  // JSON is half-typed most of the time: say it does not parse once the field is left, not on every keystroke
  const [left, setLeft] = useState(false)
  const reasonError = state.reason.trim() ? null : "a reason is required"
  const jsonError = state.choice === CUSTOM && left && toEntry(card, { ...state, reason: "-" }).error
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
            <Textarea id={`${id}-value`} className="min-h-28 font-mono text-xs" value={state.custom} onChange={(e) => { setLeft(false); touch({ custom: e.target.value }) }}
              onBlur={() => setLeft(true)} aria-invalid={!!jsonError} aria-describedby={jsonError ? `${id}-value-error` : undefined} />
            {jsonError && <p id={`${id}-value-error`} className="text-xs text-destructive">{card.id}: {jsonError}</p>}
          </div>
        ) : (
          <details>
            <summary className="cursor-pointer text-xs text-muted-foreground">value of {state.choice}</summary>
            <JsonBlock value={shown} className="mt-1 max-h-40" />
          </details>
        )}
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-reason`}>Reason (required)</Label>
          <Textarea id={`${id}-reason`} className="min-h-16" value={state.reason} onChange={(e) => touch({ reason: e.target.value })}
            aria-invalid={!!reasonError} aria-describedby={reasonError ? `${id}-reason-error` : undefined} />
          {reasonError && <p id={`${id}-reason-error`} className="text-xs text-destructive">{card.id}: {reasonError}</p>}
        </div>
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
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [waiverOpen, setWaiverOpen] = useState(false)
  const [waivers, setWaivers] = useState<Record<string, string>>(() =>   // check -> reason, written with the decisions
    Object.fromEntries((proposal.waivers ?? []).map((w) => [w.check, w.reason])))   // the ones decisions.yaml has stay unless removed
  const save = usePutDecisions(proposal.name)
  const freeze = useStartJob("freeze")
  const entries = proposal.cards.map((c) => ({ card: c, ...toEntry(c, states[c.id]) }))
  const errors = entries.filter((e) => e.error)
  const problems = save.data?.problems ?? proposal.decision_problems
  // the checker: the decisions as the form holds them, once typing has stopped; the last answer stays while it asks again
  const sent = useDebounced(JSON.stringify(entries.map((e) => e.entry)), CHECK_DEBOUNCE_MS)
  const check = useQuery({
    queryKey: evKeys.of("proposals", proposal.name, "check", sent),
    queryFn: () => evApi.checkProposal(proposal.name, JSON.parse(sent) as ReturnType<typeof toEntry>["entry"][]),
    placeholderData: keepPreviousData,
  })
  // a serious problem a person can waive (the `decision` ones are cards.validate's: they are fixed, never waived)
  const waivable = (check.data?.problems ?? []).filter((p) => p.severity === "serious" && p.check !== "decision" && !waivers[p.check])
  const freezeOff = !proposal.steps.includes("cards") ? "the proposal has no cards yet."
    : dirty ? "unsaved changes: save before freezing."
    : problems.length > 0 ? "decisions.yaml has problems freeze would refuse (above)." : null

  const onSave = (force = false) =>
    save.mutate({ decisions: entries.map((e) => e.entry), waivers: Object.entries(waivers).map(([c, reason]) => ({ check: c, reason })), base_sha256: base, force }, {
      onSuccess: (result) => { setDirty(false); setStale(false); setBase(result.sha256) },
      onError: (e) => (isConflict(e) ? setStale(true) : announceError("Saving the decisions failed", e)),
    })
  const onFreeze = () =>
    freeze.mutate({ proposal: proposal.name }, {
      onSuccess: (job) => announceJob(job, navigate),
      onError: (e) => announceError(isConflict(e) ? "Freeze refused" : "Freeze failed", e),
    })
  // the waivers go to decisions.yaml with the decisions (a plain save keeps them), then freeze runs
  const onWaiveAndFreeze = (given: { check: string; reason: string }[]) => {
    const all = { ...waivers, ...Object.fromEntries(given.map((w) => [w.check, w.reason])) }
    save.mutate({ decisions: entries.map((e) => e.entry), waivers: Object.entries(all).map(([c, reason]) => ({ check: c, reason })), base_sha256: base, force: false }, {
      onSuccess: (result) => { setDirty(false); setStale(false); setBase(result.sha256); setWaivers(all); setWaiverOpen(false); onFreeze() },
      onError: (e) => (isConflict(e) ? (setWaiverOpen(false), setStale(true)) : announceError("Saving the waivers failed", e)),
    })
  }

  const field = (c: CardT) => (
    <CardField key={c.id} card={c} state={states[c.id]} user={user ?? "you"}
      onChange={(s) => { setStates((old) => ({ ...old, [c.id]: s })); setDirty(true) }} />
  )
  const main = proposal.cards.filter((c) => !advancedCard(c))
  const advanced = proposal.cards.filter(advancedCard)
  return (
    <section className="space-y-4" aria-label="Cards">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-4">
          <div className="grid gap-4 2xl:grid-cols-2">{main.map(field)}</div>
          {advanced.length > 0 && (
            <details>
              <summary className="cursor-pointer text-sm font-medium">Advanced cards ({advanced.length}): {advanced.map((c) => c.id).join(", ")}</summary>
              <div className="mt-3 grid gap-4 2xl:grid-cols-2">{advanced.map(field)}</div>
            </details>
          )}
        </div>
        <div className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <CheckerPanel problems={check.data?.problems} pending={check.isFetching} failed={check.isError} waived={waivers} />
          <PaperPreview proposal={proposal.name} />
        </div>
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
        {config.data && !user && <span className="text-xs font-medium">No $WEBAPP_USER on the server: saving is off.</span>}
        {/* freezing is one-way (revision 1, then only `amend`): confirm it, and say why it is off */}
        <Button variant="outline" disabled={!!freezeOff || freeze.isPending} onClick={() => (waivable.length > 0 ? setWaiverOpen(true) : setConfirmOpen(true))}>
          <LockIcon data-icon="inline-start" />
          Freeze
        </Button>
        <WaiverDialog problems={waivable} open={waiverOpen} onOpenChange={setWaiverOpen} busy={save.isPending || freeze.isPending} onConfirm={onWaiveAndFreeze} />
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Freeze proposal {proposal.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                This writes protocol.yaml as revision 1 from the saved decisions. After that the cards are fixed: later changes go through{" "}
                <span className="font-mono">evidence propose amend</span> on the command line.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep editing</AlertDialogCancel>
              <AlertDialogAction onClick={onFreeze}>Freeze</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <span className="text-xs text-muted-foreground">
          {errors.length > 0 ? `${errors.length} card(s) need a reason or valid JSON. ` : save.isSuccess && !dirty ? "Saved. " : ""}
          {freezeOff ? <strong className="font-medium text-foreground">Freeze is off: {freezeOff}</strong> : "Freeze writes protocol.yaml (revision 1); after that, changes go through evidence propose amend."}
        </span>
      </div>
    </section>
  )
}
