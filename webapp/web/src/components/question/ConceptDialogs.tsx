/**
 * The two concept actions of a question: propose briefs (a job running the corpus-blind concept
 * step, row 2.1; once a question has briefs the backend proposes no more) and pick one (row 2.2,
 * recorded as the user's pick, with why). A pick can change until the gold build starts on it; a
 * change that leaves runs on the replaced concept needs `force`, which the dialog asks for.
 */
import { CheckIcon, SparklesIcon } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { usePickConcept, useProposeConcepts } from "@/api/hooks"
import type { PickedBy } from "@/api/types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { announceError, announceJob } from "@/lib/toasts"

export function ProposeDialog({ qid, disabled }: { qid: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [temperature, setTemperature] = useState("0.7")
  const [seed, setSeed] = useState("1")
  const propose = useProposeConcepts(qid)
  const navigate = useNavigate()
  const id = useId()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    propose.mutate(
      { temperature: Number(temperature), seed: Number(seed) },
      {
        onSuccess: (job) => {
          setOpen(false)
          announceJob(job, navigate, `Proposing concepts for ${qid}`)
        },
        onError: (error) => announceError("Could not start the concept step", error),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>
          <SparklesIcon data-icon="inline-start" />
          Propose concepts
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Propose concept briefs for {qid}</DialogTitle>
            <DialogDescription>
              The orchestrator model proposes up to five briefs from the question alone, without seeing the corpus. It runs as a
              job; the briefs appear here when it finishes.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor={`${id}-t`}>Temperature</Label>
              <Input id={`${id}-t`} type="number" min={0} max={2} step={0.1} required value={temperature} onChange={(e) => setTemperature(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-s`}>Seed</Label>
              <Input id={`${id}-s`} type="number" step={1} required value={seed} onChange={(e) => setSeed(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={propose.isPending}>
              {propose.isPending && <Spinner data-icon="inline-start" />}
              Start
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Who a pick from the browser is recorded as: always the person at it. `claude` and
 * `provisional-first` are set by the CLI (agent concepts pick), never here, so the hash-chained
 * concept_pick record cannot attribute a person's pick to Claude or to the automatic policy.
 */
const PICKED_BY: PickedBy = "user"

export function PickDialog({ qid, choice, title, isPicked, changes, runsOnCurrent, locked }: {
  qid: string
  choice: number
  title: string
  isPicked: boolean
  /** another brief is picked now: this pick replaces it */
  changes: boolean
  /** runs on the question's current concept (a change leaves them on the replaced one) */
  runsOnCurrent: number
  /** why the pick cannot change, if it cannot (the gold build started on it) */
  locked: string | null
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [force, setForce] = useState(false)
  const pick = usePickConcept(qid)
  const id = useId()
  const needsForce = changes && runsOnCurrent > 0

  const submit = (event: FormEvent) => {
    event.preventDefault()
    pick.mutate(
      { choice, picked_by: PICKED_BY, reason: reason.trim() || null, force: needsForce && force },
      {
        onSuccess: () => {
          setOpen(false)
          toast.success(`Picked brief ${choice} for ${qid}`, { description: title })
        },
        onError: (error) => announceError("Could not record the pick", error),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={isPicked ? "secondary" : "default"} className="w-full" disabled={isPicked || !!locked} title={locked ?? undefined}>
          <CheckIcon data-icon="inline-start" />
          {isPicked ? "Picked" : changes ? `Change the pick to brief ${choice}` : `Pick brief ${choice}`}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Pick brief {choice}</DialogTitle>
            <DialogDescription>
              “{title}” becomes the concept of {qid}: its concept.json and hash are what new runs and the gold standard use. A pick can
              change until the gold build starts on it. The pick is recorded as yours (picked by user).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor={`${id}-why`}>Reason</Label>
            <Textarea id={`${id}-why`} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why this brief answers the question best" rows={3} maxLength={2000} />
          </div>
          {needsForce && (
            <div className="flex items-start gap-2 rounded-md border border-status-warning/50 p-3">
              <Switch id={`${id}-force`} checked={force} onCheckedChange={setForce} />
              <Label htmlFor={`${id}-force`} className="text-sm leading-snug font-normal">
                {runsOnCurrent} run{runsOnCurrent === 1 ? "" : "s"} used the current concept. Change the pick anyway: they stay on the replaced
                concept and drop out of this question's counts.
              </Label>
            </div>
          )}
          <DialogFooter>
            <Button type="submit" disabled={pick.isPending || (needsForce && !force)}>
              {pick.isPending && <Spinner data-icon="inline-start" />}
              Record the pick
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
