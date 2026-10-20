/**
 * The flow's corpus step: choose a synthetic corpus under the corpora root, or build a template corpus as a job
 * (`synth build --renderer template`, no model: one corpus per chosen level plus `<name>-mixed`, with the
 * supervisor's knobs). LLM-written corpora take hours on two GPUs and are built on Slurm (runbook step 1).
 */
import { DatabaseIcon, HammerIcon } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import { isActiveJob, useCorpora, useEvConfig, useJobs, useStartJob, type SynthRequest } from "@/api/ev"
import { JobPanel } from "@/components/jobs/JobPanel"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { knobText } from "@/lib/ev"
import { isName } from "@/lib/jobs"
import { announceError, announceJob } from "@/lib/toasts"
import { cn } from "@/lib/utils"

import type { Flow } from "./flow"

const KNOBS = [
  { key: "duplicates", help: "papers that report an existing study again" },
  { key: "missing", help: "studies with a value the paper never states" },
  { key: "outliers", help: "supporting studies with an unusually large effect" },
  { key: "irrelevant", help: "papers without a treatment/control experiment" },
] as const
type Knob = (typeof KNOBS)[number]["key"]

function NumberField({ id, label, value, onChange, min, max, help }: {
  id: string; label: string; value: number; onChange: (n: number) => void; min: number; max: number; help?: string
}) {
  // The text being typed; an in-range number is passed on as it is typed, anything else is clamped
  // when the field is left (clamping per keystroke turned a cleared field into `min` and "50" into 200).
  const [draft, setDraft] = useState<string | null>(null)
  const commit = () => {
    if (draft !== null) onChange(Math.max(min, Math.min(max, Math.round(Number(draft)) || min)))
    setDraft(null)
  }
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" className="w-28" min={min} max={max} value={draft ?? value} aria-describedby={help ? `${id}-help` : undefined}
        onChange={(e) => {
          const raw = e.target.value
          setDraft(raw)
          const n = Number(raw)
          if (raw !== "" && Number.isInteger(n) && n >= min && n <= max) onChange(n)
        }}
        onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") commit() }} />
      {/* shown, not a title=: a tooltip is out of reach for touch and keyboard */}
      {help && <p id={`${id}-help`} className="w-36 text-xs text-muted-foreground">{help}</p>}
    </div>
  )
}

function SynthForm({ flow }: { flow: Flow }) {
  const config = useEvConfig()
  const levels = config.data?.levels ?? ["explicit", "paraphrased", "distributed", "complex", "contradictory"]
  const [name, setName] = useState("")
  const [seed, setSeed] = useState(1)
  const [studies, setStudies] = useState(20)
  const [chosen, setChosen] = useState<string[]>(levels)
  const [knobs, setKnobs] = useState<Record<Knob, number>>({ duplicates: 0, missing: 0, outliers: 0, irrelevant: 0 })
  const start = useStartJob("synth")
  const navigate = useNavigate()
  const ok = isName(name) && chosen.length > 0
  const blocked = !name ? "Give the corpus a name to build it." : !isName(name) ? "That name is not allowed (see the hint under Name)." : chosen.length === 0 ? "Choose at least one level." : null
  const toggle = (level: string) => setChosen((old) => (old.includes(level) ? old.filter((l) => l !== level) : [...old, level]))
  return (
    <form className="space-y-4" aria-label="Build a template corpus" onSubmit={(e) => {
      e.preventDefault()
      const body: SynthRequest = { name, seed, studies, levels: levels.filter((l) => chosen.includes(l)) as SynthRequest["levels"], ...knobs }
      start.mutate(body, {
        onSuccess: (job) => { announceJob(job, navigate); flow.set({ corpus: `${name}-mixed`, run: null }) },
        onError: (err) => announceError("The corpus build did not start", err),
      })
    }}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="grid content-start gap-1.5">
          <Label htmlFor="synth-name">Name</Label>
          <Input id="synth-name" className="w-56 font-mono" placeholder="rag-tpl-s2" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!!name && !isName(name)} aria-describedby="synth-name-hint" />
          {/* the rule lib/jobs.ts NAME_PATTERN enforces (the server's too) */}
          <p id="synth-name-hint" className={cn("w-56 text-xs", name && !isName(name) ? "text-destructive" : "text-muted-foreground")}>Letters, digits, . _ -; starts with a letter or digit, at most 128.</p>
        </div>
        <NumberField id="synth-seed" label="Seed" value={seed} onChange={setSeed} min={0} max={2 ** 31 - 1} />
        <NumberField id="synth-studies" label="Studies" value={studies} onChange={setStudies} min={1} max={200} />
      </div>
      <fieldset className="space-y-1.5">
        <legend className="text-sm font-medium">Levels (and always {name || "<name>"}-mixed)</legend>
        <div className="flex flex-wrap gap-2">
          {levels.map((l) => (
            <Button key={l} type="button" size="sm" variant={chosen.includes(l) ? "default" : "outline"} aria-pressed={chosen.includes(l)} onClick={() => toggle(l)}>{l}</Button>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-1.5">
        <legend className="text-sm font-medium">Knobs (docs/evidence-system.md F2)</legend>
        <div className="flex flex-wrap gap-3">
          {KNOBS.map((k) => (
            <NumberField key={k.key} id={`synth-${k.key}`} label={k.key} help={k.help} value={knobs[k.key]} min={0} max={50}
              onChange={(n) => setKnobs((old) => ({ ...old, [k.key]: n }))} />
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!ok || start.isPending}>
          <HammerIcon data-icon="inline-start" />
          Build template corpus
        </Button>
        <span className="text-xs text-muted-foreground">
          {blocked && <strong className="block font-medium text-foreground">{blocked}</strong>}
          Writes {chosen.length + 1} corpora under the corpora root; no model. LLM-written corpora (sub-model-1, with the blind check) take
          hours on two GPUs: build them on Slurm (docs/slurm-evidence-runbook.md step 1), they appear here when written.
        </span>
      </div>
    </form>
  )
}

export function CorpusStep({ flow }: { flow: Flow }) {
  const jobs = useJobs()
  const synthJobs = (jobs.data ?? []).filter((j) => j.kind === "synth" && isActiveJob(j))
  const corpora = useCorpora(synthJobs.length > 0)
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Corpus</CardTitle>
          <CardDescription>Chosen: {flow.corpus ? <span className="font-mono">{flow.corpus}</span> : "none yet"}. A mixed corpus holds every level's papers.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {synthJobs.map((j) => <JobPanel key={j.id} job={j} compact />)}
          {corpora.isPending ? <TableSkeleton rows={4} /> : corpora.isError ? <ErrorState error={corpora.error} onRetry={() => void corpora.refetch()} /> : corpora.data.length === 0 ? (
            <EmptyState icon={<DatabaseIcon />} title="No corpora yet" description="Build a template corpus below, or on Slurm." />
          ) : (
            <div className="max-h-96 overflow-auto rounded-md border">
              <Table aria-label="Corpora">
                <TableHeader>
                  <TableRow>{["corpus", "level", "renderer", "seed", "papers", "knobs", ""].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}</TableRow>
                </TableHeader>
                <TableBody>
                  {corpora.data.map((c) => (
                    <TableRow key={c.name} data-state={c.name === flow.corpus ? "selected" : undefined}>
                      <TableCell className="font-mono text-xs"><Link to={`/corpora/${encodeURIComponent(c.name)}`} className="hover:underline">{c.name}</Link>{c.variant && <Badge variant="outline" className="ml-1">variant</Badge>}</TableCell>
                      <TableCell className="text-xs">{c.level ?? "—"}</TableCell>
                      <TableCell className="text-xs">{c.renderer ?? "—"}</TableCell>
                      <TableCell className="text-xs tabular-nums">{c.seed ?? "—"}</TableCell>
                      <TableCell className="text-xs tabular-nums">{c.papers}</TableCell>
                      <TableCell className="text-xs">{knobText(c.settings)}</TableCell>
                      <TableCell className="text-right">
                        {c.name === flow.corpus ? <Badge>chosen</Badge> : (
                          <Button size="sm" variant="outline" onClick={() => flow.set({ corpus: c.name, run: null }, { push: true })} aria-label={`Use ${c.name}`}>Use</Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Build a template corpus</CardTitle>
          <CardDescription>synth build --renderer template: seeded ground truth from the protocol's synthesis block, papers written by templates.</CardDescription>
        </CardHeader>
        <CardContent><SynthForm flow={flow} /></CardContent>
      </Card>
    </div>
  )
}
