/**
 * A question's guided flow `/flow/:qid/:step` (the supervisor's order, STATE.md §1, §4): the selected question,
 * then protocol → corpus → run → evidence graph → answer → scores, the baselines beside the engine. Each step
 * shows what is on disk and starts what is missing as a job (webapp/evjobs.py); the choices live in the URL
 * (components/flow/flow.ts). A step whose input is not chosen yet says which one.
 */
import { CheckIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { useQuestion } from "@/api/ev"
import { QueryPage } from "@/components/ev/bits"
import { CorpusStep } from "@/components/flow/CorpusStep"
import { isStep, STEPS, useFlow, type Flow, type StepId } from "@/components/flow/flow"
import { ProtocolStep } from "@/components/flow/ProtocolStep"
import { AnswerStep, GraphStep, ScoresStep } from "@/components/flow/ResultSteps"
import { RunStep } from "@/components/flow/RunStep"
import { PageHeader } from "@/components/layout/PageHeader"
import type { Question } from "@/api/ev"
import { cn } from "@/lib/utils"

/** Whether a step's inputs are chosen, and the value it shows as chosen. */
function stepState(flow: Flow, step: StepId): { done: boolean; value: string | null } {
  switch (step) {
    case "protocol": return { done: !!flow.protocol, value: flow.protocol ? flow.protocol.name : null }
    case "corpus": return { done: !!flow.corpus, value: flow.corpus }
    case "run": return { done: !!flow.run, value: flow.run }
    default: return { done: false, value: null }
  }
}

export function Stepper({ flow, current }: { flow: Flow; current: StepId }) {
  return (
    <nav aria-label="Steps" className="overflow-x-auto">
      <ol className="flex min-w-max items-stretch gap-1 rounded-lg border p-1">
        <li className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground">
          <span className="flex size-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground"><CheckIcon className="size-3.5" /></span>
          <Link to="/" className="hover:underline">Question</Link>
        </li>
        {STEPS.map((s, n) => {
          const { done, value } = stepState(flow, s.id)
          const active = s.id === current
          return (
            <li key={s.id}>
              <Link
                to={flow.href(s.id)}
                aria-current={active ? "step" : undefined}
                className={cn("flex h-full items-center gap-2 rounded-md px-3 py-1.5 text-sm hover:bg-muted", active && "bg-muted font-medium")}
              >
                <span className={cn("flex size-6 items-center justify-center rounded-full text-xs tabular-nums", done ? "bg-primary text-primary-foreground" : "border")}>
                  {done ? <CheckIcon className="size-3.5" /> : n + 2}
                </span>
                <span>{s.label}</span>
                {/* muted-foreground on the active step's bg-muted falls under 4.5:1 */}
                {value && <span className={cn("max-w-40 truncate font-mono text-xs", active ? "text-foreground/80" : "text-muted-foreground")} title={value}>{value}</span>}
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function FlowView({ question, step }: { question: Question; step: StepId }) {
  const flow = useFlow(question)
  return (
    <div className="space-y-6">
      <PageHeader title={<span className="text-balance">{question.question}</span>} docTitle={question.id} description={<>Question <span className="font-mono">{question.id}</span>: choose its protocol, a corpus, run the engine and the baselines, then read the evidence graph, the answer and the scores.</>} />
      <Stepper flow={flow} current={step} />
      {step === "protocol" && <ProtocolStep flow={flow} />}
      {step === "corpus" && <CorpusStep flow={flow} />}
      {step === "run" && <RunStep flow={flow} />}
      {step === "graph" && <GraphStep flow={flow} />}
      {step === "answer" && <AnswerStep flow={flow} />}
      {step === "scores" && <ScoresStep flow={flow} />}
    </div>
  )
}

export default function FlowPage() {
  const { qid = "", step } = useParams()
  const question = useQuestion(qid)
  return (
    <QueryPage query={question} what={`question ${qid}`} back={{ to: "/", label: "All questions" }}>
      {(q) => <FlowView question={q} step={isStep(step) ? step : "protocol"} />}
    </QueryPage>
  )
}
