/**
 * The proposal's eight choice-point cards as a form (docs/evidence-system.md Part E): per card an option (or a
 * custom value in the card's shape, as JSON) and a reason, which is required. A card keeps the `by` it has in
 * decisions.yaml (the model's default, or whoever edited it by hand) until the user touches it; then it is the
 * app's user ($WEBAPP_USER). Save writes decisions.yaml (PUT, in the format evidence/propose/cards.py validates)
 * with the file's sha256 as the form loaded it: if the file changed since, the server refuses and the form offers
 * reload or overwrite. It shows what `evidence propose freeze` would refuse; Freeze starts that command as a job
 * once the saved decisions pass. Amendments after the freeze stay on the command line.
 *
 * Each card shows the checker's problems that belong to it; the checker beside the cards links each problem to its
 * card (opening the advanced cards when it is one of them). Save and Freeze stay in reach in a bar under the cards.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CircleCheckIcon, InfoIcon, LockIcon, OctagonXIcon, SaveIcon, UserCheckIcon } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router"

import { isConflict } from "@/api/client"
import { evApi, evKeys, useEvConfig, usePutDecisions, useStartJob, type Card as CardT, type CheckProblem, type ProposalDetail } from "@/api/ev"
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
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useDebounced } from "@/hooks/use-debounced"
import { announceError, announceJob } from "@/lib/toasts"
import { cn } from "@/lib/utils"

import { CheckerPanel } from "./CheckerPanel"
import { CUSTOM, advancedCard, initialState, optionValue, toEntry, type CardState } from "./cards"
import { PaperPreview } from "./PaperPreview"
import { WaiverDialog } from "./WaiverDialog"

/** The checker waits for the typing to stop (the endpoint re-applies every decision to the draft). */
export const CHECK_DEBOUNCE_MS = 400

/** How long a card the checker sent you to stays marked. */
const MARK_MS = 1600

const cardDom = (id: string) => `card-${id}`

function CardField({ card, state, onChange, user, checks, marked }: {
  card: CardT
  state: CardState
  onChange: (s: CardState) => void
  user: string
  /** the live checker's problems that belong to this card */
  checks: CheckProblem[]
  /** the checker just sent the person here */
  marked: boolean
}) {
  const touch = (patch: Partial<CardState>) => onChange({ ...state, ...patch, by: user })
  // JSON is half-typed most of the time: say it does not parse once the field is left, not on every keystroke
  const [left, setLeft] = useState(false)
  const reasonError = state.reason.trim() ? null : "A reason is required: say in a sentence why this choice fits the question."
  const jsonError = state.choice === CUSTOM && left && toEntry(card, { ...state, reason: "-" }).error
  const id = cardDom(card.id)
  const shown = state.choice === CUSTOM ? null : optionValue(card, state.choice)
  const serious = checks.some((p) => p.severity === "serious")
  const byModel = state.by === "model"
  return (
    <Card id={id} tabIndex={-1} size="sm" role="group" aria-labelledby={`${id}-title`}
      className={cn("min-w-0 scroll-mt-20 outline-none transition-shadow duration-(--motion-base)", serious && "ring-destructive/50", marked && "ring-2 ring-primary")}>
      <CardHeader>
        <CardTitle id={`${id}-title`} className="flex flex-wrap items-center gap-2 text-sm">
          {card.title ?? card.id}
          <Badge variant={byModel ? "outline" : "secondary"}>
            {!byModel && <UserCheckIcon aria-hidden="true" />}
            {byModel ? "model's default" : `decided by ${state.by}`}
          </Badge>
          {state.choice !== card.default && <Badge>changed from the default</Badge>}
        </CardTitle>
        <CardDescription>{card.ask}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {checks.length > 0 && (
          <ul className="space-y-1.5 rounded-md bg-muted/60 p-2 text-sm" aria-label={`Checker on ${card.title ?? card.id}`}>
            {checks.map((p) => (
              <li key={`${p.check}-${p.message}`} className="flex gap-2">
                {p.severity === "serious"
                  ? <OctagonXIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                  : <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
                <span><span className="sr-only">{p.severity === "serious" ? "Serious: " : "Worth a look: "}</span>{p.message}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor={`${id}-choice`}>Choice</Label>
          <Select value={state.choice} onValueChange={(choice) => touch({ choice })}>
            <SelectTrigger id={`${id}-choice`} aria-label={`Choice for ${card.id}`} aria-describedby={`${id}-default`} className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {card.options.map((o) => (
                <SelectItem key={String(o.id)} value={String(o.id)}>{String(o.id)}: {String(o.summary ?? "")}</SelectItem>
              ))}
              <SelectItem value={CUSTOM}>custom: a value of my own (JSON)</SelectItem>
            </SelectContent>
          </Select>
          <p id={`${id}-default`} className="text-xs text-muted-foreground">
            The model's default is <span className="font-mono">{card.default}</span>{card.rationale ? `: ${card.rationale}` : "."}
          </p>
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
            <summary className="text-xs text-muted-foreground">What <span className="font-mono">{state.choice}</span> sets in the protocol</summary>
            <JsonBlock value={shown} className="mt-1 max-h-40" />
          </details>
        )}
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-reason`}>Reason (required)</Label>
          <Textarea id={`${id}-reason`} className="min-h-16" value={state.reason} onChange={(e) => touch({ reason: e.target.value })} required
            aria-invalid={!!reasonError} aria-describedby={reasonError ? `${id}-reason-error` : `${id}-reason-help`} />
          {reasonError
            ? <p id={`${id}-reason-error`} className="text-xs text-destructive">{reasonError}</p>
            : <p id={`${id}-reason-help`} className="text-xs text-muted-foreground">Saved in decisions.yaml with the choice and who made it.</p>}
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
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [marked, setMarked] = useState<string | null>(null)   // the card the checker sent the person to
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
  const checks = check.data?.problems ?? []
  // a serious problem a person can waive (the `decision` ones are cards.validate's: they are fixed, never waived)
  const waivable = checks.filter((p) => p.severity === "serious" && p.check !== "decision" && !waivers[p.check])
  const freezeOff = !proposal.steps.includes("cards") ? "the proposal has no cards yet."
    : dirty ? "save your changes first."
    : problems.length > 0 ? "decisions.yaml has problems freeze would refuse (listed above)." : null
  const titles = Object.fromEntries(proposal.cards.map((c) => [c.id, c.title ?? c.id]))
  const advancedIds = new Set(proposal.cards.filter(advancedCard).map((c) => c.id))

  // the checker's "Go to card": open the advanced fold if needed, then bring the card into view and focus its choice
  const pending = useRef<string | null>(null)
  const [jumps, setJumps] = useState(0)   // one per "Go to card", so going to the same card again scrolls again
  const showCard = (id: string) => {
    if (advancedIds.has(id)) setAdvancedOpen(true)
    pending.current = id
    setMarked(id)
    setJumps((n) => n + 1)
  }
  useEffect(() => {   // after the render that opened the fold: the card is in the page now
    const id = pending.current
    if (!id) return
    pending.current = null
    const el = document.getElementById(cardDom(id))
    const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    el?.scrollIntoView?.({ block: "center", behavior: smooth ? "smooth" : "auto" })
    const field = document.getElementById(`${cardDom(id)}-choice`)
    ;(field ?? el)?.focus({ preventScroll: true })
  }, [jumps])
  useEffect(() => {
    if (!marked) return
    const t = setTimeout(() => setMarked(null), MARK_MS)
    return () => clearTimeout(t)
  }, [marked, jumps])

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
    <CardField key={c.id} card={c} state={states[c.id]} user={user ?? "you"} marked={marked === c.id}
      checks={checks.filter((p) => p.card === c.id)}
      onChange={(s) => { setStates((old) => ({ ...old, [c.id]: s })); setDirty(true) }} />
  )
  const main = proposal.cards.filter((c) => !advancedCard(c))
  const advanced = proposal.cards.filter(advancedCard)
  const advancedSerious = checks.filter((p) => p.severity === "serious" && p.card && advancedIds.has(p.card)).length
  const changed = proposal.cards.filter((c) => states[c.id].choice !== c.default).length
  const byPeople = proposal.cards.filter((c) => states[c.id].by !== "model").length
  return (
    <section className="space-y-4" aria-label="Cards">
      <div className="space-y-1">
        <h3 className="text-base font-semibold">Decide the cards</h3>
        <p className="max-w-prose text-sm text-muted-foreground">
          Each card is one open choice in the protocol. Keep the model's default or pick another option, and say why. The checker
          re-checks the draft each time you stop typing.
        </p>
        <p className="text-xs text-muted-foreground">
          {proposal.cards.length} cards: {changed} changed from the default, {byPeople} decided by a person.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-4">
          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">{main.map(field)}</div>
          {advanced.length > 0 && (
            <details open={advancedOpen} onToggle={(e) => setAdvancedOpen(e.currentTarget.open)} className="rounded-xl border border-dashed px-4 py-2">
              <summary className="text-sm font-medium">
                Advanced cards ({advanced.length}): {advanced.map((c) => c.id).join(", ")}
                {advancedSerious > 0 && <Badge variant="destructive" className="ml-2">{advancedSerious} serious</Badge>}
              </summary>
              <p className="mt-1 text-xs text-muted-foreground">How the engine screens and locates; most protocols keep the model's defaults here.</p>
              <div className="mt-3 grid grid-cols-1 gap-4 pb-2 2xl:grid-cols-2">{advanced.map(field)}</div>
            </details>
          )}
        </div>
        <div className="min-w-0 space-y-4 xl:sticky xl:top-16 xl:self-start">
          <CheckerPanel problems={check.data?.problems} pending={check.isFetching} failed={check.isError} waived={waivers}
            cardTitles={titles} onShowCard={showCard} />
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
      {/* in reach while scrolling the cards: stuck to the bottom of the screen until the form ends */}
      <div className="sticky bottom-0 z-10 -mx-1 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border bg-background/95 p-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <Button onClick={() => onSave()} disabled={errors.length > 0 || save.isPending || !user}>
          {save.isPending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : <SaveIcon data-icon="inline-start" aria-hidden="true" />}
          Save decisions
        </Button>
        {/* freezing is one-way (revision 1, then only `amend`): confirm it, and say why it is off */}
        <Button variant="outline" disabled={!!freezeOff || freeze.isPending} aria-describedby="cards-status"
          onClick={() => (waivable.length > 0 ? setWaiverOpen(true) : setConfirmOpen(true))}>
          {freeze.isPending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : <LockIcon data-icon="inline-start" aria-hidden="true" />}
          Freeze
        </Button>
        <p id="cards-status" role="status" className="min-w-0 flex-1 text-sm">
          {config.data && !user ? <span className="font-medium">No $WEBAPP_USER on the server: saving is off.</span>
            : errors.length > 0 ? <span className="text-destructive">{errors.length} card(s) need a reason or valid JSON.</span>
            : freezeOff ? <span className="text-muted-foreground">{dirty ? "Unsaved changes. " : ""}Freeze is off: {freezeOff}</span>
            : (
              <span className="flex items-center gap-1.5 text-muted-foreground">
                {save.isSuccess && <CircleCheckIcon className="size-4 shrink-0 text-status-good" aria-hidden="true" />}
                {save.isSuccess ? "Saved. " : ""}{waivable.length > 0 ? `Freezing asks you to waive ${waivable.length} serious problem(s).` : "Ready to freeze: it writes the protocol as revision 1."}
              </span>
            )}
        </p>
        <WaiverDialog problems={waivable} open={waiverOpen} onOpenChange={setWaiverOpen} busy={save.isPending || freeze.isPending} onConfirm={onWaiveAndFreeze}
          cardTitles={titles} user={user} />
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
      </div>
    </section>
  )
}
