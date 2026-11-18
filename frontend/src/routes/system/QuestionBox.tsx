/** Box 2: the question, its sub-questions and how the answer is made. "Draft the protocol" asks for the plan in
 * one call (the question, the sub-questions, the answer kind and its target); a question of the domain's file that
 * has a batch plan can open that plan instead. Done when the plan view exists. */
import { useState } from "react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import { openBatchPlan, startPlan, useAction, type PlanView } from "../plan/api"
import { parseSubQuestions, SubQuestionsBox } from "../plan/SubQuestionsBox"
import type { SystemDomain } from "./api"
import { Box } from "./PickBox"

const SELECT = "h-9 rounded-md border bg-background px-2 text-sm"
const KINDS: [string, string][] = [
  ["written", "Written by a model from the facts (any question)"],
  ["effect", "effect"],
  ["consistency", "consistency"],
  ["inventory", "inventory"],
  ["best", "best"],
]
const TARGETS = ["condition", "metric"]

export function QuestionBox({ open, domain, seed, onView, onError }: {
  open: boolean
  domain: SystemDomain | undefined
  seed: number | null
  onView: (view: PlanView) => void
  onError: (message: string | null) => void
}) {
  const [picked, setPicked] = useState("")
  const [question, setQuestion] = useState("")
  const [subText, setSubText] = useState("")
  const [kind, setKind] = useState("written")
  const [target, setTarget] = useState("condition")
  const done = (v: PlanView) => { onError(null); onView(v) }
  const fail = (e: unknown) => onError(e instanceof Error ? e.message : String(e))
  const draft = useAction(() => startPlan(question, parseSubQuestions(subText), { answer_by: kind, target: kind === "inventory" ? target : null }), done, fail)
  const batchOpen = useAction((qid: string) => openBatchPlan(domain?.domain ?? "", qid), done, fail)
  const busy = draft.isPending || batchOpen.isPending
  const fromFile = domain?.questions.find((q) => q.id === picked)

  const pick = (id: string) => {
    setPicked(id)
    const q = domain?.questions.find((x) => x.id === id)
    if (!q) return
    setQuestion(q.question)
    setSubText(q.sub_questions.join("\n"))
    setKind(KINDS.some(([k]) => k === q.kind) ? q.kind : "written")
    setTarget(q.target ?? "condition")
  }

  return (
    <Box title="2. Question" open={open}>
      <div className="space-y-3">
        <label className="flex flex-wrap items-center gap-2 text-sm font-medium">
          <span>Use a question from the domain's file</span>
          <select aria-label="Use a question from the domain's file" className={SELECT} value={picked} onChange={(e) => pick(e.target.value)}>
            <option value="">None</option>
            {(domain?.questions ?? []).map((q) => <option key={q.id} value={q.id}>{q.id}: {q.question}</option>)}
          </select>
        </label>
        <Input aria-label="Question" placeholder="What do you want to know?" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <SubQuestionsBox value={subText} onChange={setSubText} />
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="font-medium">How the answer is made</span>
            <select aria-label="How the answer is made" className={SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map(([k, text]) => <option key={k} value={k}>{text}</option>)}
            </select>
          </label>
          {kind === "inventory" && (
            <label className="flex items-center gap-2">
              <span className="font-medium">Target</span>
              <select aria-label="Target" className={SELECT} value={target} onChange={(e) => setTarget(e.target.value)}>
                {TARGETS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={busy || !question.trim() || seed === null} onClick={() => draft.mutate(undefined)}>Draft the protocol</Button>
          {fromFile && fromFile.plan !== "missing" && (
            <>
              <Button variant="outline" disabled={busy} onClick={() => batchOpen.mutate(fromFile.id)}>Open its batch plan</Button>
              <Link className="text-sm underline" to={`/plan?batch=${domain?.domain}/${fromFile.id}`}>edit on the plan page</Link>
            </>
          )}
        </div>
      </div>
    </Box>
  )
}
