/**
 * The claim walk (plan "Frontend pages" 4, Answer tab): fact -> claim(s) -> the step that made
 * each claim (the model call's numbers, never its reasoning; the command; the head of its output)
 * -> the passage of the corpus file with the claim's quote highlighted and scrolled into view.
 * This is the "easier to check" of the thesis in one panel.
 *
 * A fact opens GET .../facts/{id}/walk: one request, with the verdicts scoring counted. When a
 * verdict is missing (the run is not scored yet, or the judge was down), "Ask the judge" asks
 * for the walk again with `judge=true`. Claims without a fact (a graph edge no answer fact cites)
 * are assembled here from the run's claims and steps and GET /api/corpus for each passage.
 */
import { ArrowDownIcon, ExternalLinkIcon, FileTextIcon, GavelIcon, QuoteIcon, TerminalIcon, TriangleAlertIcon } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"

import { urls } from "@/api/client"
import { useClaims, useFactWalk, usePassage, useSteps } from "@/api/hooks"
import type { Claim, FactWalk, Passage, Step, Verdict, WalkClaim } from "@/api/types"
import { StatusBadge } from "@/components/badges"
import { EmptyState, ErrorState } from "@/components/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { factStatus, FACT_STATUS_LABEL, term } from "@/lib/facts"
import { duration, int } from "@/lib/format"
import { splitPassage } from "@/lib/passage"

import { FactStatusIcon } from "./FactBadge"
import type { WalkTarget } from "./walk-context"

export function ClaimWalkSheet({ runId, target, onClose }: { runId: string; target: WalkTarget | null; onClose: () => void }) {
  return (
    <Sheet open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        {target?.kind === "fact" && <FactWalkView key={target.factId} runId={runId} factId={target.factId} />}
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
  const [judge, setJudge] = useState(false)
  const scored = useFactWalk(runId, factId)
  const judged = useFactWalk(runId, judge ? factId : null, { judge: true })
  const walk = judge && judged.data ? judged : scored
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
  return (
    <FactWalkBody
      walk={walk.data}
      runId={runId}
      judge={{ asking: judge && judged.isFetching, error: judge ? judged.error : null, ask: () => (judge ? void judged.refetch() : setJudge(true)) }}
    />
  )
}

interface JudgeAction {
  asking: boolean
  error: unknown
  ask: () => void
}

export function FactWalkBody({ walk, runId, judge }: { walk: FactWalk; runId: string; judge?: JudgeAction }) {
  const { fact } = walk
  const status = factStatus(fact, walk.label)
  const missingVerdict = walk.claims.some((c) => c.claim && !c.support)
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
              {judge && missingVerdict && (
                <Button size="xs" variant="outline" onClick={judge.ask} disabled={judge.asking}>
                  {judge.asking ? <Spinner data-icon="inline-start" /> : <GavelIcon data-icon="inline-start" />}
                  Ask the judge
                </Button>
              )}
            </div>
            {walk.support && <VerdictView verdict={walk.support} title="Best verdict over the fact's quotes" />}
            {judge?.error ? <div className="mt-2"><ErrorState error={judge.error} title="The judge could not be asked" /></div> : null}
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
            walk.claims.map((item) => <WalkClaimChain key={item.claim_id} runId={runId} item={item} />)
          )}
        </ol>
      </div>
    </>
  )
}

const ANCHOR_STATUS: Record<string, string> = {
  relocated: "The quote has moved in today's corpus file; the passage shows where it is now.",
  ambiguous: "The quote occurs more than once in today's corpus file; the passage shows the occurrence nearest its offsets.",
  broken: "The quote is no longer in today's corpus file: the anchor is broken.",
  missing: "This id is not an accepted claim of the run.",
  unknown: "The backend has no corpus configured ($CORPUS), so the passage cannot be shown.",
}

function WalkClaimChain({ runId, item }: { runId: string; item: WalkClaim }) {
  if (!item.claim) {
    return (
      <WalkStep icon={<TriangleAlertIcon />} title={`Claim ${item.claim_id}`}>
        <p className="text-sm text-muted-foreground">{ANCHOR_STATUS[item.anchor_status] ?? ANCHOR_STATUS.missing}</p>
      </WalkStep>
    )
  }
  return (
    <ClaimChain
      runId={runId}
      claim={item.claim}
      step={item.step}
      passage={item.passage}
      verdict={item.support ?? null}
      anchorNote={item.anchor_status !== "ok" ? (ANCHOR_STATUS[item.anchor_status] ?? `Anchor: ${item.anchor_status}.`) : null}
    />
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
              step={steps.data?.find((s) => s.step === claim.step && s.agent_id === claim.agent_id) ?? null}
            />
          ))}
        </ol>
      </div>
    </>
  )
}

function ClaimWithPassage({ runId, claim, step }: { runId: string; claim: Claim; step: Step | null }) {
  const passage = usePassage(claim.paper_id, claim.anchor?.start ?? 0, claim.anchor?.end ?? 0, !!claim.anchor)
  return (
    <ClaimChain
      runId={runId}
      claim={claim}
      step={step}
      passage={passage.data ?? null}
      passageError={passage.error}
      passageLoading={passage.isLoading}
      verdict={null}
      anchorNote={claim.anchor ? null : "The claim has no anchor in the corpus."}
    />
  )
}

function ClaimChain({ runId, claim, step, passage, passageError, passageLoading, verdict, anchorNote }: {
  runId: string
  claim: Claim
  step: Step | null
  passage: Passage | null
  passageError?: unknown
  passageLoading?: boolean
  verdict: Verdict | null
  anchorNote: string | null
}) {
  return (
    <>
      <WalkStep icon={<ArrowDownIcon />} title={`Claim ${claim.claim_id ?? "(rejected)"}`}>
        <Triple s={claim.s} p={claim.p} o={claim.o} />
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {claim.file && <Badge variant="outline" className="font-mono font-normal">{claim.file}</Badge>}
          <span>step {claim.step}</span>
          <span>agent {claim.agent_id}</span>
          <span>origin {claim.origin}</span>
          {claim.anchor && <span className="tabular-nums">chars {claim.anchor.start}–{claim.anchor.end}</span>}
        </div>
        {verdict && <VerdictView verdict={verdict} title="Verdict on this quote" />}
      </WalkStep>
      <WalkStep icon={<TerminalIcon />} title={step ? `Step ${step.step} · ${step.agent_id} · ${step.phase ?? step.origin}` : `Step ${claim.step}`}>
        {step ? <StepView runId={runId} step={step} /> : <p className="text-sm text-muted-foreground">The step record is missing.</p>}
      </WalkStep>
      <WalkStep icon={<FileTextIcon />} title="Passage">
        {anchorNote && (
          <Alert className="mb-2 py-2">
            <TriangleAlertIcon />
            <AlertDescription className="text-xs">{anchorNote}</AlertDescription>
          </Alert>
        )}
        {passage ? (
          <PassageView passage={passage} />
        ) : passageError ? (
          <ErrorState error={passageError} title="Could not load the passage" />
        ) : passageLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : !anchorNote ? (
          <p className="text-sm text-muted-foreground">No passage.</p>
        ) : null}
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

function Triple({ s, p, o }: { s: unknown; p: unknown; o: unknown }) {
  return (
    <p className="flex flex-wrap items-center gap-1.5 font-mono text-sm">
      <Badge variant="secondary" className="font-mono">{term(s)}</Badge>
      <span className="text-muted-foreground">{term(p)}</span>
      <Badge variant="secondary" className="max-w-full font-mono whitespace-normal">{term(o)}</Badge>
    </p>
  )
}

const VERDICT_WORD = { supports: "supports", partial: "partial", no: "does not support" } as const

function VerdictView({ verdict, title }: { verdict: Verdict; title: string }) {
  return (
    <div className="mt-2 rounded-md border bg-muted/30 p-2 text-sm">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p>
        <span className="font-medium">Judge: {VERDICT_WORD[verdict.label] ?? verdict.label}.</span> {verdict.rationale}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {[verdict.model, verdict.source === "judge" ? "asked now" : verdict.source === "score" ? "as scored" : null, verdict.cached ? "cached" : null, verdict.prompt_sha256 ? `prompt ${verdict.prompt_sha256.slice(0, 12)}` : null]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </div>
  )
}

/** The model call's numbers (no reasoning: it is never recorded), the command and its output head. */
export function StepView({ runId, step }: { runId: string; step: Pick<Step, "step" | "agent_id" | "model_call" | "command" | "exit_code" | "timed_out" | "output_head" | "output_bytes"> }) {
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
          {call.error && <Stat label="error" value={call.error} />}
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
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              exit {step.exit_code ?? "—"}
              {step.timed_out ? " · timed out" : ""} · {int(step.output_bytes)} bytes
            </span>
            <a href={urls.stepOutput(runId, step.step, step.agent_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
              full output <ExternalLinkIcon className="size-3" aria-hidden="true" />
            </a>
          </div>
          {step.output_head !== null && step.output_head !== undefined && (
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
        {passage.title && passage.title !== passage.paper_id ? ` · ${passage.title}` : ""}
        <span className="tabular-nums"> · chars {int(passage.offset)}–{int(passage.offset + [...passage.text].length)} of {int(passage.length)}</span>
      </figcaption>
      <blockquote className="max-h-80 overflow-auto rounded-md border bg-card p-3 font-serif text-sm leading-relaxed whitespace-pre-wrap" tabIndex={0} aria-label={`Passage of ${passage.paper_id}`}>
        {parts.before}
        {parts.match && <mark ref={mark} data-testid="quote">{parts.match}</mark>}
        {parts.after}
      </blockquote>
      {parts.clamped && <p className="text-xs text-status-serious">The anchor lies partly outside this window of the file.</p>}
    </figure>
  )
}

