/**
 * "New run" (plan "Frontend pages" 3): POST /api/runs starts a job that runs `agent run` on a
 * question's picked concept (or a concept file), then for claim_off the attach step, then verify,
 * pairs, graph, export-prov and score. "Both conditions" starts a claim_on and a claim_off job with
 * the same seed, the pair the Compare page puts side by side (jobs of a kind run one at a time).
 *
 * Budget fields left empty use the agent's defaults. When a run the app did not start is live (a
 * batch on the cluster), the backend refuses with 409; the dialog then offers to start anyway.
 * The sandbox defaults to landlock; unsandboxed (tests only) has to be confirmed.
 */
import { PlayIcon, TriangleAlertIcon } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { isConflict } from "@/api/client"
import { useQuestions, useStartRun } from "@/api/hooks"
import type { Condition, Job, RunRequest } from "@/api/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Switch } from "@/components/ui/switch"
import { announceError } from "@/lib/toasts"

type ConditionChoice = Condition | "both"

interface Form {
  source: "question" | "file"
  qid: string
  conceptPath: string
  condition: ConditionChoice
  temperature: string
  seed: string
  steps: string
  tokens: string
  sandbox: "landlock" | "unsandboxed"
  attach: boolean
}

const optionalInt = (value: string) => (value.trim() === "" ? null : Number(value))

export function NewRunDialog({ defaultQid }: { defaultQid?: string }) {
  const [open, setOpen] = useState(false)
  const questions = useQuestions()
  const start = useStartRun()
  const navigate = useNavigate()
  const id = useId()
  const [conflict, setConflict] = useState<string | null>(null)
  const [form, setForm] = useState<Form>({
    source: "question", qid: defaultQid ?? "", conceptPath: "", condition: "claim_on", temperature: "0.7", seed: "1",
    steps: "", tokens: "", sandbox: "landlock", attach: true,
  })
  const set = <K extends keyof Form>(key: K, value: Form[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    setConflict(null)
  }
  // unsandboxed (tests only) needs an explicit yes
  const [unsandboxedOk, setUnsandboxedOk] = useState(false)
  const picked = questions.data?.filter((q) => q.concept.status === "picked") ?? []
  const ready = (form.source === "question" ? !!form.qid : !!form.conceptPath.trim()) && (form.sandbox === "landlock" || unsandboxedOk)

  const requestFor = (condition: Condition, force: boolean): RunRequest => ({
    ...(form.source === "question" ? { qid: form.qid } : { concept_path: form.conceptPath.trim() }),
    condition,
    temperature: Number(form.temperature),
    seed: Number(form.seed),
    steps: optionalInt(form.steps),
    tokens: optionalInt(form.tokens),
    sandbox: form.sandbox,
    attach: condition === "claim_off" ? form.attach : false,
    force,
  })

  const announce = (jobs: Job[]) => {
    const [first] = jobs
    toast.success(jobs.length > 1 ? `Started ${jobs.length} runs (jobs ${jobs.map((j) => j.id).join(", ")})` : `Started a run: job ${first.id} ${first.state}`, {
      description: "The run appears in the list once its directory exists; follow its log on the Jobs page.",
      action: first.run_id ? { label: "Open run", onClick: () => navigate(`/earlier/runs/${encodeURIComponent(first.run_id!)}`) } : { label: "Open log", onClick: () => navigate(`/earlier/jobs/${first.id}`) },
    })
  }

  const submit = async (force = false) => {
    const conditions: Condition[] = form.condition === "both" ? ["claim_on", "claim_off"] : [form.condition]
    const started: Job[] = []
    try {
      for (const condition of conditions) started.push(await start.mutateAsync(requestFor(condition, force)))
      setOpen(false)
      setConflict(null)
      announce(started)
    } catch (error) {
      if (started.length) announce(started)
      // only the "a batch is live" refusal can be overridden (its message names `force`)
      if (isConflict(error) && !force && error instanceof Error && /\bforce\b/.test(error.message)) setConflict(error.message)
      else announceError("Could not start the run", error)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit(false)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setConflict(null) }}>
      <DialogTrigger asChild>
        <Button>
          <PlayIcon data-icon="inline-start" />
          New run
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={onSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>New run</DialogTitle>
            <DialogDescription>
              Runs the agent on a concept as a job on the server, then verifies, builds the graph and scores it against the question's key.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor={`${id}-source`}>Concept</Label>
              <Select value={form.source} onValueChange={(v) => set("source", v as Form["source"])}>
                <SelectTrigger id={`${id}-source`} className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="question">A question's picked concept</SelectItem>
                  <SelectItem value="file">A concept.json file (under $CONCEPTS or $RUNS)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.source === "question" ? (
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor={`${id}-qid`}>Question</Label>
                <Select value={form.qid} onValueChange={(v) => set("qid", v)}>
                  <SelectTrigger id={`${id}-qid`} className="w-full"><SelectValue placeholder={questions.isPending ? "Loading…" : "Pick a question"} /></SelectTrigger>
                  <SelectContent>
                    {picked.map((q) => (
                      <SelectItem key={q.id} value={q.id}>
                        <span className="font-mono">{q.id}</span> · {q.concept.title ?? q.question}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {questions.data && picked.length === 0 && <p className="text-xs text-muted-foreground">No question has a picked concept yet: pick one on its question page first.</p>}
              </div>
            ) : (
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor={`${id}-path`}>Concept file</Label>
                <Input id={`${id}-path`} className="font-mono" placeholder="concepts/q01/concept.json" value={form.conceptPath} onChange={(e) => set("conceptPath", e.target.value)} />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor={`${id}-condition`}>Condition</Label>
              <Select value={form.condition} onValueChange={(v) => set("condition", v as ConditionChoice)}>
                <SelectTrigger id={`${id}-condition`} className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="claim_on">claim on</SelectItem>
                  <SelectItem value="claim_off">claim off (baseline)</SelectItem>
                  <SelectItem value="both">both, same seed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-sandbox`}>Sandbox</Label>
              <Select value={form.sandbox} onValueChange={(v) => { set("sandbox", v as Form["sandbox"]); setUnsandboxedOk(false) }}>
                <SelectTrigger id={`${id}-sandbox`} className="w-full" aria-describedby={`${id}-sandbox-help`}><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="landlock">landlock</SelectItem>
                  <SelectItem value="unsandboxed">unsandboxed (tests only)</SelectItem>
                </SelectContent>
              </Select>
              <p id={`${id}-sandbox-help`} className="text-xs text-muted-foreground">
                landlock: the agent's commands read the corpus and write only their scratch directory.
              </p>
            </div>
            {form.sandbox === "unsandboxed" && (
              <Alert className="border-status-serious/60 sm:col-span-2">
                <TriangleAlertIcon className="text-status-serious" />
                <AlertTitle>Unsandboxed is for tests only</AlertTitle>
                <AlertDescription>
                  <p>
                    The agent's commands run with network and write access. config.json records it, and the run is marked unsandboxed on
                    every page; it is no thesis run.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Switch id={`${id}-unsandboxed-ok`} checked={unsandboxedOk} onCheckedChange={setUnsandboxedOk} />
                    <Label htmlFor={`${id}-unsandboxed-ok`} className="font-normal">Run it without the sandbox</Label>
                  </div>
                </AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor={`${id}-t`}>Temperature</Label>
              <Input id={`${id}-t`} type="number" min={0} max={2} step={0.1} required value={form.temperature} onChange={(e) => set("temperature", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-seed`}>Seed</Label>
              <Input id={`${id}-seed`} type="number" step={1} required value={form.seed} onChange={(e) => set("seed", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-steps`}>Step budget</Label>
              <Input id={`${id}-steps`} type="number" min={1} step={1} placeholder="agent default" value={form.steps} onChange={(e) => set("steps", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${id}-tokens`}>Token budget</Label>
              <Input id={`${id}-tokens`} type="number" min={1} step={1000} placeholder="agent default" value={form.tokens} onChange={(e) => set("tokens", e.target.value)} />
            </div>
            {form.condition !== "claim_on" && (
              <div className="flex items-center gap-2 sm:col-span-2">
                <Switch id={`${id}-attach`} checked={form.attach} onCheckedChange={(v) => set("attach", v)} />
                <Label htmlFor={`${id}-attach`}>Run the attach step after the claim_off run</Label>
              </div>
            )}
          </div>
          {conflict && (
            <Alert>
              <TriangleAlertIcon />
              <AlertTitle>The server did not start the run</AlertTitle>
              <AlertDescription>
                <p>{conflict}</p>
                <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => void submit(true)} disabled={start.isPending}>
                  Start anyway
                </Button>
              </AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button type="submit" disabled={!ready || start.isPending}>
              {start.isPending ? <Spinner data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
              {form.condition === "both" ? "Start both runs" : "Start run"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
