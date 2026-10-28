/**
 * A question's guided flow `/flow/:qid/:step` (the supervisor's order, STATE.md §1, §4): the selected question,
 * then protocol → corpus → run → evidence graph → answer, the baselines beside the engine. Each step
 * shows what is on disk and starts what is missing as a job (webapp/evjobs.py); the choices live in the URL
 * (components/flow/flow.ts). A step whose input is not chosen yet says which one.
 */
import { useParams, useSearchParams } from "react-router"

import { useActiveJobs, useProposal, useQuestion } from "@/api/ev"
import { QueryPage } from "@/components/ev/bits"
import { CorpusStep } from "@/components/flow/CorpusStep"
import { isStep, useFlow, type StepId } from "@/components/flow/flow"
import { ProtocolStep } from "@/components/flow/ProtocolStep"
import { TYPED_FLOW } from "@/components/flow/QuestionStep"
import { AnswerStep, GraphStep } from "@/components/flow/ResultSteps"
import { RunStep } from "@/components/flow/RunStep"
import { StepFooter, StepHeader, Stepper } from "@/components/flow/Stepper"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import type { Question } from "@/api/ev"

/** The stepper moved to components/flow/Stepper; kept here for imports of the old place. */
export { Stepper }

function FlowView({ question, step }: { question: Question; step: StepId }) {
  const flow = useFlow(question)
  return (
    <div className="space-y-6">
      <PageHeader
        title={<span className="text-balance">{question.question}</span>}
        docTitle={question.id}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span>Question <span className="font-mono">{question.id}</span></span>
            {question.kind && <Badge variant="outline">{question.kind} question</Badge>}
          </span>
        }
      />
      <Stepper flow={flow} current={step} />
      <section aria-labelledby="step-title" className="space-y-6">
        <StepHeader step={step} />
        {/* a new step's content rises in once (200ms): it says the page moved on; nothing moves under reduced motion */}
        <div key={step} className="duration-(--motion-base) motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1">
          {step === "protocol" && <ProtocolStep flow={flow} />}
          {step === "corpus" && <CorpusStep flow={flow} />}
          {step === "run" && <RunStep flow={flow} />}
          {step === "graph" && <GraphStep flow={flow} />}
          {step === "answer" && <AnswerStep flow={flow} />}
        </div>
        <StepFooter flow={flow} step={step} />
      </section>
    </div>
  )
}

/**
 * A question the person typed (`/flow/typed/...?proposal=name`): it has no entry in the questions file, so its
 * question is what the proposal's frame asks and its kind what the frame (or the person) says.
 */
function TypedFlow({ step }: { step: StepId }) {
  const [params] = useSearchParams()
  const name = params.get("proposal") ?? ""
  const jobs = useActiveJobs({ proposal: name })
  const proposal = useProposal(name, jobs.length > 0)
  const frame = proposal.data?.frame
  const kind = (["effect", "inventory", "consistency", "best"] as const).find((k) => k === frame?.kind) ?? "effect"
  const question: Question = {
    id: TYPED_FLOW, question: typeof frame?.question === "string" ? frame.question : "Your question", kind,
    protocol: null, agentic_protocol: null, proposals: name ? [name] : [],
  }
  return <FlowView question={question} step={step} />
}

export default function FlowPage() {
  const { qid = "", step } = useParams()
  const question = useQuestion(qid === TYPED_FLOW ? "" : qid)
  if (qid === TYPED_FLOW) return <TypedFlow step={isStep(step) ? step : "protocol"} />
  return (
    <QueryPage query={question} what={`question ${qid}`} back={{ to: "/", label: "All questions" }}>
      {(q) => <FlowView question={q} step={isStep(step) ? step : "protocol"} />}
    </QueryPage>
  )
}
