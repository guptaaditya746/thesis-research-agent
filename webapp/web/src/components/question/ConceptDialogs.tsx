/**
 * The two concept actions of a question: propose briefs (a job running the corpus-blind
 * concept step, row 2.1) and pick one (row 2.2, recorded with who picked it and why).
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { announceError, announceJob } from "@/lib/toasts"

export function ProposeDialog({ qid, hasBriefs }: { qid: string; hasBriefs: boolean }) {
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
        <Button variant={hasBriefs ? "outline" : "default"}>
          <SparklesIcon data-icon="inline-start" />
          {hasBriefs ? "Propose again" : "Propose concepts"}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Propose concept briefs for {qid}</DialogTitle>
            <DialogDescription>
              The orchestrator model proposes up to five briefs without seeing the corpus. Runs as a job; new briefs replace the
              shown ones when it finishes.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor={`${id}-t`}>Temperature</Label>
              <Input id={`${id}-t`} type="number" min={0} max={2} step={0.1} required value={temperature} onChange={(e) => setTemperature(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-s`}>Seed</Label>
              <Input id={`${id}-s`} type="number" min={0} step={1} required value={seed} onChange={(e) => setSeed(e.target.value)} />
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

const PICKERS: { value: PickedBy; label: string }[] = [
  { value: "user", label: "user (you)" },
  { value: "claude", label: "claude" },
  { value: "provisional-first", label: "provisional-first" },
]

export function PickDialog({ qid, choice, title, isPicked }: { qid: string; choice: number; title: string; isPicked: boolean }) {
  const [open, setOpen] = useState(false)
  const [pickedBy, setPickedBy] = useState<PickedBy>("user")
  const [reason, setReason] = useState("")
  const pick = usePickConcept(qid)
  const id = useId()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    pick.mutate(
      { choice, picked_by: pickedBy, reason: reason.trim() },
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
        <Button variant={isPicked ? "secondary" : "default"} className="w-full" disabled={isPicked}>
          <CheckIcon data-icon="inline-start" />
          {isPicked ? "Picked" : `Pick brief ${choice}`}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Pick brief {choice}</DialogTitle>
            <DialogDescription>
              “{title}” becomes the concept of {qid}: its concept.json and hash are what new runs and the gold key use. Change a
              pick before the gold standard is built.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor={`${id}-by`}>Picked by</Label>
            <Select value={pickedBy} onValueChange={(v) => setPickedBy(v as PickedBy)}>
              <SelectTrigger id={`${id}-by`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PICKERS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${id}-why`}>Reason</Label>
            <Textarea id={`${id}-why`} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why this brief answers the question best" rows={3} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={pick.isPending}>
              {pick.isPending && <Spinner data-icon="inline-start" />}
              Record the pick
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
