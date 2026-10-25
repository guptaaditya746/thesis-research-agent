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
import { Textarea } from "@/components/ui/textarea"
import { announceError, announceJob } from "@/lib/toasts"

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
              placeholder="Which retriever is best on long documents?" />
          </div>
          <Button type="submit" disabled={!ok || start.isPending}>
            <SparklesIcon data-icon="inline-start" />
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
      <section aria-label="Questions" className="space-y-3">
        {questions.isPending ? <CardsSkeleton count={1} /> : questions.isError ? <ErrorState error={questions.error} title="The questions file does not validate" /> : questions.data.length === 0 ? (
          <EmptyState icon={<ListOrderedIcon />} title="No questions" description={`Add one to ${config.data?.questions.path ?? "evidence/questions.yaml"}.`} />
        ) : questions.data.map((q) => (
          <Card key={q.id} className="relative">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-lg text-balance">
                <Link to={`/flow/${encodeURIComponent(q.id)}`} className="after:absolute after:inset-0 hover:underline">{q.question}</Link>
                <ArrowRightIcon className="size-4 text-muted-foreground" aria-hidden="true" />
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{q.id}</span>
                <Badge variant="outline">{q.kind}</Badge>
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
