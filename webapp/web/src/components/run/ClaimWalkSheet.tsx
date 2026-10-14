/**
 * The claim walk (plan "Frontend pages" 4, Answer tab): fact -> claim(s) -> the step that
 * made each claim (the model call's stats, never its reasoning; the command; the head of its
 * output) -> the passage of the corpus file with the claim's quote highlighted and scrolled
 * into view. This is the "easier to check" of the thesis in one panel.
 *
 * A fact opens GET .../facts/{id}/walk (one request, with the judge's verdict). Claims without
 * a fact (a graph edge no answer fact cites) are assembled here from the run's claims and
 * steps and GET /api/corpus for each passage.
 */
import { ArrowDownIcon, ExternalLinkIcon, FileTextIcon, QuoteIcon, TerminalIcon } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { urls } from "@/api/client"
import { useClaims, useFactWalk, usePassage, useSteps } from "@/api/hooks"
import type { Claim, FactWalk, Passage, Step, Verdict } from "@/api/types"
import { StatusBadge } from "@/components/badges"
import { EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { factStatus, FACT_STATUS_LABEL } from "@/lib/facts"
import { duration, int } from "@/lib/format"
import { splitPassage } from "@/lib/passage"

import { FactStatusIcon } from "./FactBadge"
import type { WalkTarget } from "./walk-context"

export function ClaimWalkSheet({ runId, target, onClose }: { runId: string; target: WalkTarget | null; onClose: () => void }) {
  return (
    <Sheet open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        {target?.kind === "fact" && <FactWalkView runId={runId} factId={target.factId} />}
        {target?.kind === "claims" && <ClaimsWalkView runId={runId} claimIds={target.claimIds} label={target.label} />}
      </SheetContent>
    </Sheet>
  )
}

function Header({ title, description }: { title: ReactNode; description: ReactNode }) {
  return (
    <SheetHeader className="border-b pr-12">
      <SheetTitle>{title}</SheetTitle>
      <SheetDescription asChild>
        <div>{description}</div>
      </SheetDescription>
    </SheetHeader>
  )
}

function WalkSkeleton() {
  return (
    <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading the claim walk">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

function FactWalkView({ runId, factId }: { runId: string; factId: string }) {
  const walk = useFactWalk(runId, factId)
  if (walk.isPending) {
    return (
      <>
        <Header title={`Claim walk · ${factId}`} description="Loading…" />
        <WalkSkeleton />
      </>
    )
  }
  if (walk.isError) {
    return (
      <>
        <Header title={`Claim walk · ${factId}`} description="The walk could not be loaded." />
        <div className="p-4"><ErrorState error={walk.error} onRetry={() => void walk.refetch()} /></div>
      </>
    )
  }
  return <FactWalkBody walk={walk.data} runId={runId} />
}

export function FactWalkBody({ walk, runId }: { walk: FactWalk; runId: string }) {
  const { fact } = walk
  const status = factStatus(fact, walk.support)
  return (
    <>
      <Header
        title={
          <span className="flex items-center gap-2">
            Claim walk · <span className="font-mono">{fact.id}</span>
          </span>
        }
        description={`Row ${walk.row_id} · ${fact.claims.length} claim${fact.claims.length === 1 ? "" : "s"} · origin ${fact.origin}`}
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <ol className="space-y-4" aria-label="Claim walk">
          <WalkStep icon={<QuoteIcon />} title="Fact">
            <Triple s={fact.s} p={fact.p} o={fact.o} />
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <StatusBadge tone="neutral" icon={<FactStatusIcon status={status} />}>{FACT_STATUS_LABEL[status]}</StatusBadge>
            </div>
            {walk.support && <VerdictView verdict={walk.support} />}
          </WalkStep>
          {walk.claims.length === 0 ? (
            <li>
              <EmptyState
                title="No claim behind this fact"
                description={
                  fact.origin === "attach"
                    ? "The attach step looked for a quote afterwards and answered “no source found”."
                    : "The agent put this fact in the answer without recording a claim for it."
                }
              />
            </li>
          ) : (
            walk.claims.map(({ claim, step, passage }) => (
              <ClaimChain key={claim.claim_id ?? claim.quote} runId={runId} claim={claim} step={step} passage={passage} />
            ))
          )}
        </ol>
      </div>
    </>
  )
}

function ClaimsWalkView({ runId, claimIds, label }: { runId: string; claimIds: string[]; label?: string }) {
  const claims = useClaims(runId)
  const steps = useSteps(runId)
  const title = `Claim walk · ${label ?? claimIds.join(", ")}`
  if (claims.isPending || steps.isPending) {
    return (
      <>
        <Header title={title} description="Loading…" />
        <WalkSkeleton />
      </>
    )
  }
  const error = claims.error ?? steps.error
  if (error) {
    return (
      <>
        <Header title={title} description="The walk could not be loaded." />
        <div className="p-4"><ErrorState error={error} /></div>
      </>
    )
  }
  const found = claimIds.map((id) => claims.data?.find((c) => c.claim_id === id)).filter((c): c is Claim => !!c)
  return (
    <>
      <Header title={title} description={`${found.length} claim${found.length === 1 ? "" : "s"}; no answer fact cites ${found.length === 1 ? "it" : "them"}.`} />
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <ol className="space-y-4" aria-label="Claim walk">
          {found.map((claim) => (
            <ClaimWithPassage
              key={claim.claim_id}
              runId={runId}
              claim={claim}
              step={steps.data?.find((s) => s.step === claim.step && s.agent_id === claim.agent_id)}
            />
          ))}
        </ol>
      </div>
    </>
  )
}

function ClaimWithPassage({ runId, claim, step }: { runId: string; claim: Claim; step: Step | undefined }) {
  const passage = usePassage(claim.paper_id, claim.anchor?.start ?? 0, claim.anchor?.end ?? 0, !!claim.anchor)
  return <ClaimChain runId={runId} claim={claim} step={step} passage={passage.data} passageError={passage.error} />
}

function ClaimChain({ runId, claim, step, passage, passageError }: {
  runId: string
  claim: Claim
  step: Step | undefined
  passage: Passage | undefined
  passageError?: unknown
}) {
  return (
    <>
      <WalkStep icon={<ArrowDownIcon />} title={`Claim ${claim.claim_id ?? "(rejected)"}`}>
        <Triple s={claim.s} p={claim.p} o={claim.o} />
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="font-mono font-normal">{claim.file}</Badge>
          <span>step {claim.step}</span>
          <span>agent {claim.agent_id}</span>
          <span>origin {claim.origin}</span>
          {claim.anchor && <span className="tabular-nums">chars {claim.anchor.start}–{claim.anchor.end}</span>}
        </div>
      </WalkStep>
      <WalkStep icon={<TerminalIcon />} title={step ? `Step ${step.step} · ${step.agent_id} · ${step.phase}` : `Step ${claim.step}`}>
        {step ? <StepView runId={runId} step={step} /> : <p className="text-sm text-muted-foreground">The step record is missing.</p>}
      </WalkStep>
      <WalkStep icon={<FileTextIcon />} title="Passage">
        {passage ? (
          <PassageView passage={passage} />
        ) : passageError ? (
          <ErrorState error={passageError} title="Could not load the passage" />
        ) : (
          <Skeleton className="h-32 w-full" />
        )}
      </WalkStep>
    </>
  )
}

function WalkStep({ icon, title, children }: { icon: ReactNode; title: ReactNode; children: ReactNode }) {
  return (
    <li className="relative border-l pb-1 pl-6">
      <span className="absolute top-0 -left-3 flex size-6 items-center justify-center rounded-full border bg-background text-muted-foreground [&>svg]:size-3.5" aria-hidden="true">
        {icon}
      </span>
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      {children}
    </li>
  )
}

function Triple({ s, p, o }: { s: string; p: string; o: string | number | boolean }) {
  return (
    <p className="flex flex-wrap items-center gap-1.5 font-mono text-sm">
      <Badge variant="secondary" className="font-mono">{s}</Badge>
      <span className="text-muted-foreground">{p}</span>
      <Badge variant="secondary" className="max-w-full font-mono whitespace-normal">{String(o)}</Badge>
    </p>
  )
}

function VerdictView({ verdict }: { verdict: Verdict }) {
  return (
    <div className="mt-2 rounded-md border bg-muted/30 p-2 text-sm">
      <p>
        <span className="font-medium">Judge: {verdict.label}.</span> {verdict.rationale}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {verdict.model}
        {verdict.cached ? " · cached" : ""} · prompt {verdict.prompt_sha256.slice(0, 12)}
      </p>
    </div>
  )
}

/** The model call's numbers (no reasoning: it is never recorded), the command and its output head. */
export function StepView({ runId, step }: { runId: string; step: Step }) {
  const call = step.model_call
  return (
    <div className="space-y-2 text-sm">
      {call && (
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <Stat label="tokens" value={int(call.tokens)} />
          <Stat label="time" value={duration(call.seconds)} />
          <Stat label="parse" value={call.parse ?? "—"} />
          <Stat label="reply" value={call.reply ?? "—"} />
          <Stat label="finish" value={call.finish_reason ?? "—"} />
        </dl>
      )}
      {step.command && (
        <pre className="max-h-48 overflow-auto rounded-md bg-muted p-2 font-mono text-xs whitespace-pre-wrap">
          <span className="text-muted-foreground select-none">$ </span>
          {step.command}
        </pre>
      )}
      {step.command && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              exit {step.exit_code ?? "—"}
              {step.timed_out ? " · timed out" : ""} · {int(step.output_bytes)} bytes
            </span>
            <a href={urls.stepOutput(runId, step.step)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
              full output <ExternalLinkIcon className="size-3" aria-hidden="true" />
            </a>
          </div>
          {step.output_head !== null && (
            <pre className="max-h-40 overflow-auto rounded-md border p-2 font-mono text-xs whitespace-pre-wrap">{step.output_head || "(no output)"}</pre>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-1">
      <dt>{label}</dt>
      <dd className="font-medium text-foreground tabular-nums">{value}</dd>
    </div>
  )
}

/** The passage with the quote marked; the mark is scrolled into view when it appears. */
export function PassageView({ passage }: { passage: Passage }) {
  const mark = useRef<HTMLElement>(null)
  const parts = splitPassage(passage)
  useEffect(() => {
    mark.current?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [passage])
  return (
    <figure className="space-y-1">
      <figcaption className="text-xs text-muted-foreground">
        <span className="font-mono">{passage.paper_id}</span>
        {passage.title ? ` · ${passage.title}` : ""}
      </figcaption>
      <blockquote className="max-h-80 overflow-auto rounded-md border bg-card p-3 font-serif text-sm leading-relaxed whitespace-pre-wrap" tabIndex={0}>
        {parts.before}
        <mark ref={mark} data-testid="quote">{parts.match}</mark>
        {parts.after}
      </blockquote>
      {parts.clamped && <p className="text-xs text-status-serious">The anchor lies partly outside this window of the file.</p>}
    </figure>
  )
}
