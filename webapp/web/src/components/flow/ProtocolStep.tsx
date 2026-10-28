/**
 * The flow's protocol step: choose the protocol the run will use (the question's hand-written protocol, its
 * agentic variant, or a frozen proposal), see it, or propose one (evidence propose frame → draft → critic →
 * cards as one model job, resumed from the first missing step), decide the eight cards and freeze.
 */
import { CheckIcon, FileCode2Icon, PlayIcon, SparklesIcon } from "lucide-react"
import { useState, type ReactNode } from "react"
import { Link, useNavigate } from "react-router"

import {
  useActiveJobs,
  useEvConfig,
  useProposal,
  useProposals,
  useProtocol,
  useStartJob,
  type ProposalDetail,
  type ProtocolRef,
} from "@/api/ev"
import { CriticChecks, Frame, ProposalSteps } from "@/components/ev/ProposalParts"
import { ProtocolPanel } from "@/components/ev/ProtocolPanel"
import { JobPanel } from "@/components/jobs/JobPanel"
import { CardsSkeleton, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { isName, protocolParam } from "@/lib/jobs"
import { announceError, announceJob } from "@/lib/toasts"
import { cn } from "@/lib/utils"

import { CardsForm } from "./CardsForm"
import { KindConfirm } from "./KindConfirm"
import { TYPED_FLOW } from "./QuestionStep"
import { protocolLabel, type Flow } from "./flow"

function ChosenProtocol({ protocol }: { protocol: ProtocolRef }) {
  const repo = useProtocol(protocol.source === "repo" ? protocol.name : "")
  const proposal = useProposal(protocol.source === "proposal" ? protocol.name : "")
  const query = protocol.source === "repo" ? repo : proposal
  if (query.isPending) return <CardsSkeleton count={1} />
  if (query.isError) return <ErrorState error={query.error} />
  const view = protocol.source === "repo" ? repo.data : proposal.data?.protocol
  if (!view) return <p className="text-sm text-muted-foreground">Proposal {protocol.name} is not frozen yet: decide its cards and freeze it.</p>
  return <ProtocolPanel view={view} />
}

function Choice({ flow, value, title, children, href }: { flow: Flow; value: ProtocolRef; title: string; children?: ReactNode; href: string }) {
  const chosen = flow.protocol?.source === value.source && flow.protocol.name === value.name
  return (
    <li className={cn("flex flex-wrap items-center gap-2 rounded-lg border p-3 text-sm transition-colors duration-(--motion-fast)", chosen && "border-primary bg-primary/5")}>
      <FileCode2Icon className={cn("size-4", chosen ? "text-primary" : "text-muted-foreground")} aria-hidden="true" />
      <span className="font-medium">{title}</span>
      <Link to={href} className="inline-flex min-h-6 items-center font-mono text-xs underline underline-offset-2">{value.name}</Link>
      {children}
      <span className="flex-1" />
      {chosen ? <Badge><CheckIcon aria-hidden="true" />chosen</Badge> : (
        <Button size="sm" variant="outline" onClick={() => flow.set({ protocol: protocolParam(value), run: null }, { push: true })} aria-label={`Use ${value.source === "repo" ? "protocol" : "proposal"} ${value.name}`}>Use</Button>
      )}
    </li>
  )
}

function ProposeForm({ flow }: { flow: Flow }) {
  const config = useEvConfig()
  const proposals = useProposals()
  const taken = new Set((proposals.data ?? []).map((p) => p.name))
  const suggestion = (() => {
    for (let n = 1; ; n++) if (!taken.has(`${flow.question.id}-p${n}`)) return `${flow.question.id}-p${n}`
  })()
  const [name, setName] = useState("")
  const [model, setModel] = useState("")
  const start = useStartJob("propose")
  const navigate = useNavigate()
  const proposal = name || suggestion
  const ok = isName(proposal)
  return (
    <form className="flex flex-wrap items-start gap-3" onSubmit={(e) => {
      e.preventDefault()
      start.mutate({ proposal, question: flow.question.id, model: model || config.data?.default_model || "orch-model" }, {
        onSuccess: (job) => { announceJob(job, navigate); flow.set({ proposal }) },
        onError: (err) => announceError("The proposal flow did not start", err),
      })
    }}>
      <div className="grid w-full gap-1.5 sm:w-56">
        <Label htmlFor="proposal-name">Proposal name</Label>
        <Input id="proposal-name" className="font-mono" placeholder={suggestion} value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!ok}
          aria-describedby={ok ? undefined : "proposal-name-error"} />
        {!ok && <p id="proposal-name-error" className="text-xs text-destructive">Letters, digits, dots, dashes and underscores, starting with a letter or digit.</p>}
      </div>
      <div className="grid w-full gap-1.5 sm:w-40">
        <Label htmlFor="proposal-model">Model</Label>
        <Input id="proposal-model" className="font-mono" placeholder={config.data?.default_model ?? "orch-model"} value={model} onChange={(e) => setModel(e.target.value)} />
      </div>
      {/* sm:mt-6 lines the button up with the fields under their labels */}
      <Button type="submit" className="sm:mt-6" disabled={!ok || start.isPending}>
        {start.isPending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : <SparklesIcon data-icon="inline-start" aria-hidden="true" />}
        Propose a protocol
      </Button>
    </form>
  )
}

function Workbench({ flow, name }: { flow: Flow; name: string }) {
  const jobs = useActiveJobs({ proposal: name })
  const proposal = useProposal(name, jobs.length > 0)
  const resume = useStartJob("propose")
  const [loaded, setLoaded] = useState(0)   // bumped to start the cards form again from the file
  const config = useEvConfig()
  const navigate = useNavigate()
  const p: ProposalDetail | undefined = proposal.data
  const typed = flow.question.id === TYPED_FLOW   // asked by its text: the frame holds it
  const frameQuestion = typeof p?.frame?.question === "string" ? p.frame.question : null
  const kind = String(p?.frame?.kind ?? "effect")
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          Proposal <Link to={`/proposals/${encodeURIComponent(name)}`} className="font-mono underline">{name}</Link>
          {p && <ProposalSteps steps={p.steps} />}
        </CardTitle>
        <CardDescription>
          Frame, draft, critic and cards (three model calls, cached in the proposal directory), then the cards are yours to decide.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {jobs.map((j) => <JobPanel key={j.id} job={j} compact />)}
        {proposal.isError && !jobs.length && (
          <p className="text-sm text-muted-foreground">
            Proposal {name} has no frame yet: the model has not framed the question{proposal.error instanceof Error ? ` (${proposal.error.message})` : ""}.
          </p>
        )}
        {proposal.isPending && !jobs.length && <CardsSkeleton count={1} className="md:grid-cols-1 xl:grid-cols-1" />}
        {p && !p.frozen && !p.steps.includes("cards") && !jobs.length && (!typed || frameQuestion) && (
          <Button size="sm" variant="outline" disabled={resume.isPending}
            onClick={() => resume.mutate({ proposal: name, ...(typed ? { text: frameQuestion ?? "" } : { question: flow.question.id }), model: config.data?.default_model ?? "orch-model" }, {
              onSuccess: (job) => announceJob(job, navigate), onError: (e) => announceError("Resume failed", e),
            })}>
            <PlayIcon data-icon="inline-start" />
            Resume from the first missing step
          </Button>
        )}
        {p?.frame && p.steps.includes("frame") && <KindConfirm proposal={p} />}
        {p?.frame && (
          <details>
            <summary className="text-sm font-medium">How the model framed the question</summary>
            <div className="mt-2"><Frame frame={p.frame} /></div>
          </details>
        )}
        {p && p.checks.length > 0 && (
          <details open={!p.steps.includes("cards")}>
            <summary className="text-sm font-medium">The critic's checks of the draft: {p.checks.filter((c) => !c.ok).length} of {p.checks.length} fail</summary>
            <div className="mt-2"><CriticChecks checks={p.checks} /></div>
          </details>
        )}
        {p && p.steps.includes("cards") && !p.frozen && <CardsForm key={`${p.name}-${kind}-${loaded}`} proposal={p}
          onReload={() => void proposal.refetch().then(() => setLoaded((n) => n + 1))} />}
        {p?.frozen && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge>frozen</Badge>
            <span>revision {p.revision} · <span className="font-mono text-xs">{p.protocol_sha256?.slice(0, 16)}</span></span>
            <Button size="sm" onClick={() => flow.set({ protocol: protocolParam({ source: "proposal", name }), run: null }, { push: true })}>Use this protocol</Button>
            <span className="text-xs text-muted-foreground">Amendments: <span className="font-mono">evidence propose amend $EV/proposals/{name} --reason …</span> on the command line.</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function ProtocolStep({ flow }: { flow: Flow }) {
  const q = flow.question
  const proposals = useProposals()
  const mine = (proposals.data ?? []).filter((p) => q.proposals.includes(p.name))
  const working = !!flow.proposal
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2 text-base">
            Protocols for this question {q.kind && <Badge variant="outline" title="what the question asks">{q.kind}</Badge>}
          </CardTitle>
          <CardDescription>Chosen: {protocolLabel(flow.protocol)}. {q.protocol ? "" : "This question has no hand-written protocol: propose one below."}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {proposals.isError && <ErrorState error={proposals.error} title="Could not list the proposals" onRetry={() => void proposals.refetch()} />}
          <ul className="space-y-2">
            {q.protocol && <Choice flow={flow} value={{ source: "repo", name: q.protocol }} title="Hand-written" href={`/protocol/${encodeURIComponent(q.protocol)}`} />}
            {q.agentic_protocol && (
              <Choice flow={flow} value={{ source: "repo", name: q.agentic_protocol }} title="Hand-written, agentic extractor last" href={`/protocol/${encodeURIComponent(q.agentic_protocol)}`} />
            )}
            {mine.map((p) => p.frozen ? (
              <Choice key={p.name} flow={flow} value={{ source: "proposal", name: p.name }} title="Proposal" href={`/proposals/${encodeURIComponent(p.name)}`}>
                <Badge variant="outline">frozen, revision {p.revision}</Badge>
              </Choice>
            ) : (
              <li key={p.name} className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed p-3 text-sm">
                <span className="font-medium">Proposal</span>
                <span className="font-mono text-xs">{p.name}</span>
                <Badge variant="outline">{p.steps.at(-1) ?? "started"}: not frozen</Badge>
                <span className="flex-1" />
                {flow.proposal === p.name ? <Badge variant="secondary">open below</Badge> : (
                  <Button size="sm" variant="outline" onClick={() => flow.set({ proposal: p.name }, { push: true })}>Work on it</Button>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {flow.proposal && <Workbench flow={flow} name={flow.proposal} />}
      {q.id !== TYPED_FLOW && <Card>
        <CardHeader>
          <CardTitle className="text-base">{working ? "Propose another protocol" : "Propose a protocol"}</CardTitle>
          <CardDescription>
            The model frames the question, drafts a protocol from the example one, checks it with a critic and turns its open choices into
            eight cards, each with the model's default, for you to decide. It runs as one model job; nothing uses the proposed protocol until
            you freeze it and choose it here.
          </CardDescription>
        </CardHeader>
        <CardContent><ProposeForm flow={flow} /></CardContent>
      </Card>}
      {flow.protocol && (
        <section aria-label="Chosen protocol">
          {/* every evidence type's fields: long, so it opens on request instead of pushing the step's actions away */}
          <details className="rounded-xl border bg-card px-4 py-2">
            <summary className="text-sm font-medium">Show the chosen protocol in full: {protocolLabel(flow.protocol)}</summary>
            <div className="mt-3 pb-2"><ChosenProtocol protocol={flow.protocol} /></div>
          </details>
        </section>
      )}
    </div>
  )
}
