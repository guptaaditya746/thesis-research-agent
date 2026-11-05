/**
 * The flow's first step: pick one of the questions of the questions file (each with its kind), or type your own.
 * A typed question has no hand-written protocol: it starts the proposal job (frame, draft, critic, cards) and
 * opens `/flow/typed/protocol?proposal=<name>`, where its kind is confirmed and its cards are decided.
 */
import { ArrowRightIcon, ListOrderedIcon, SparklesIcon } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import { useEvConfig, useProposals, useQuestions, useStartJob } from "@/api/ev"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { announceError, announceJob } from "@/lib/toasts"

import { TOTAL_STEPS } from "./flow"

/** The backend's shortest typed question (ProposeRequest.text). */
export const MIN_QUESTION = 10

export const TYPED_FLOW = "typed"

function TypedQuestion() {
  const [text, setText] = useState("")
  const config = useEvConfig()
  const proposals = useProposals()
  const start = useStartJob("propose")
  const navigate = useNavigate()
  const taken = new Set((proposals.data ?? []).map((p) => p.name))
  let n = 1
  while (taken.has(`typed-p${n}`)) n++
  const proposal = `typed-p${n}`
  const ok = text.trim().length >= MIN_QUESTION
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Or type your own question</CardTitle>
        <CardDescription>
          The model frames it, guesses its kind and drafts a protocol with the cards of that kind for you to decide. It runs as one model job.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form aria-label="Your own question" className="space-y-3" onSubmit={(e) => {
          e.preventDefault()
          start.mutate({ proposal, text: text.trim(), model: config.data?.default_model ?? "orch-model" }, {
            onSuccess: (job) => {
              announceJob(job, navigate)
              void navigate(`/flow/${TYPED_FLOW}/protocol?proposal=${encodeURIComponent(proposal)}`)
            },
            onError: (err) => announceError("The proposal flow did not start", err),
          })
        }}>
          <div className="grid gap-1.5">
            <Label htmlFor="typed-question">Question</Label>
            <Textarea id="typed-question" className="min-h-16" maxLength={600} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Type your own question about these papers" aria-describedby="typed-question-help" />
            <p id="typed-question-help" className="text-xs text-muted-foreground">
              At least {MIN_QUESTION} characters{text.trim().length > 0 && !ok ? ` (${MIN_QUESTION - text.trim().length} to go)` : ""}. Up to 600.
            </p>
          </div>
          <Button type="submit" disabled={!ok || start.isPending}>
            {start.isPending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : <SparklesIcon data-icon="inline-start" aria-hidden="true" />}
            Propose a protocol
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export function QuestionStep() {
  const config = useEvConfig()
  const questions = useQuestions()
  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <p className="text-xs font-semibold tracking-wide text-primary uppercase">Step 1 of {TOTAL_STEPS}</p>
        <h2 className="text-lg font-semibold tracking-tight">Pick a research question</h2>
        <p className="max-w-prose text-sm text-muted-foreground">Open one of the questions below, or type your own and let the model propose a protocol for it.</p>
      </header>
      <section aria-label="Questions" className="space-y-3">
        {questions.isPending ? <CardsSkeleton count={1} className="md:grid-cols-1 xl:grid-cols-1" /> : questions.isError ? (
          <ErrorState error={questions.error} title="The questions file does not validate" onRetry={() => void questions.refetch()} />
        ) : questions.data.length === 0 ? (
          <EmptyState icon={<ListOrderedIcon />} title="No questions" description={`Add one to ${config.data?.questions.path ?? "evidence/questions.yaml"}, or type your own below.`} />
        ) : questions.data.map((q) => (
          // the whole card is the link's target (after:inset-0); its ring shows where keyboard focus is
          <Card key={q.id} className="relative transition-colors duration-(--motion-fast) hover:bg-muted/50 has-[a:focus-visible]:ring-3 has-[a:focus-visible]:ring-ring/50">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-lg text-balance">
                <Link to={`/flow/${encodeURIComponent(q.id)}`} className="outline-none after:absolute after:inset-0 hover:underline">{q.question}</Link>
                <ArrowRightIcon className="size-4 text-primary" aria-hidden="true" />
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{q.id}</span>
                {q.kind && <Badge variant="outline" title="the kind of question">{q.kind}</Badge>}
                {q.protocol ? <Badge variant="secondary">hand-written protocol {q.protocol}</Badge> : <Badge variant="outline">no protocol yet: propose one</Badge>}
                {q.agentic_protocol && <Badge variant="outline">agentic variant</Badge>}
                {q.proposals.length > 0 && <Badge variant="outline">{q.proposals.length} proposal(s)</Badge>}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </section>
      <TypedQuestion />
    </div>
  )
}
