/**
 * The planner on one page (the "Best Author Run" mockup): a question box, the plan (evidence lines, the
 * main-answer rule, the decisions panel), Run (disabled until every decision is confirmed) and the results in
 * place: each line's result ("No evidence found", or "failed: <reason>"), the answer ("missing: <line>" for a
 * line that failed), and the reruns that flip the answer. No pilot run: an empty answer is a valid answer.
 */
import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router"

import { PageHeader } from "@/components/layout/PageHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

import { confirmAll, decide, deleteLine, openBatchPlan, RULES, sendAnswers, setMainRule, startPlan, startRun, useAction, usePlanResult, type PlanResult, type PlanView, type Rerun } from "./api"
import { DecisionsPanel } from "./DecisionsPanel"
import { LineCard } from "./LineCard"
import { parseSubQuestions, SubQuestionsBox } from "./SubQuestionsBox"

export function Clarify({ view, busy, onSend }: { view: PlanView; busy: boolean; onSend: (a: { question: string; answer: string }[]) => void }) {
  const [picked, setPicked] = useState<Record<string, string>>({})
  const done = view.clarifications.every((c) => picked[c.question])
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">A question first</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {view.clarifications.map((c) => (
          <fieldset key={c.question} className="space-y-1">
            <legend className="text-sm font-medium">{c.question}</legend>
            <div className="flex flex-wrap gap-2">
              {c.options.map((o) => (
                <Button key={o} size="sm" variant={picked[c.question] === o ? "default" : "outline"} aria-pressed={picked[c.question] === o}
                  onClick={() => setPicked({ ...picked, [c.question]: o })}>{o}</Button>
              ))}
            </div>
          </fieldset>
        ))}
        <Button disabled={!done || busy} onClick={() => onSend(view.clarifications.map((c) => ({ question: c.question, answer: picked[c.question] })))}>Make the plan</Button>
      </CardContent>
    </Card>
  )
}

function MainRule({ rule, busy, onChange }: { rule: string; busy: boolean; onChange: (rule: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(rule)
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-medium">Main answer rule:</span>
      {editing ? (
        <form className="flex flex-1 gap-2" onSubmit={(e) => { e.preventDefault(); onChange(draft); setEditing(false) }}>
          <select aria-label="Main answer rule" className="h-9 flex-1 rounded-md border bg-background px-2 text-sm" value={draft} onChange={(e) => setDraft(e.target.value)}>
            {Object.entries(RULES).map(([name, text]) => <option key={name} value={name}>{name}: {text}</option>)}
          </select>
          <Button type="submit" size="sm" disabled={busy}>Save</Button>
        </form>
      ) : (
        <>
          <span>{rule}: {RULES[rule] ?? ""}</span>
          <Button variant="link" size="sm" onClick={() => setEditing(true)}>change</Button>
        </>
      )}
    </div>
  )
}

function Labels({ labels, lines }: { labels: Record<string, string>; lines: { id: string; question: string }[] }) {
  const shown = lines.filter((l) => labels[l.id])
  if (shown.length === 0) return null
  return (
    <ul aria-label="How solid each line is" className="text-sm">
      {shown.map((l) => <li key={l.id}>{l.question}: <span className="font-medium">{labels[l.id]}</span></li>)}
    </ul>
  )
}

function Links({ links }: { links: NonNullable<PlanResult["links"]> }) {
  if (links.length === 0) return null
  return (
    <ul aria-label="Builds on" className="text-sm">
      {links.map((l, i) => <li key={`${l.paper}:${i}`}>{l.paper} {l.relation} {l.ref}: <span className="text-muted-foreground">{l.text}</span></li>)}
    </ul>
  )
}

function Reruns({ reruns }: { reruns: Rerun[] }) {
  const flipping = reruns.filter((r) => r.flips)
  if (flipping.length === 0) return null
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Settings that change the answer</CardTitle></CardHeader>
      <CardContent>
        <table className="w-full text-left text-sm">
          <thead><tr><th className="font-medium">Setting</th><th className="font-medium">Result</th></tr></thead>
          <tbody>
            {flipping.map((r, i) => (
              <tr key={`${r.setting}:${i}`}><td>{r.setting}</td><td>flips the answer</td></tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

export default function PlanPage() {
  const [question, setQuestion] = useState("")
  const [subText, setSubText] = useState("")
  const [params] = useSearchParams()
  const batch = params.get("batch")
  const [view, setView] = useState<PlanView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const take = (v: PlanView) => { setError(null); setView(v) }
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e))
  const useMutationOf = <A, R = PlanView>(fn: (arg: A) => Promise<R>, done: (r: R) => void = take as unknown as (r: R) => void) => useAction(fn, done, fail)

  const start = useMutationOf((a: { question: string; subs: string[] }) => startPlan(a.question, a.subs))
  const opener = useMutationOf((b: string) => { const [domain, qid] = b.split("/"); return openBatchPlan(domain, qid) })
  const opened = useRef<string | null>(null)
  const openBatch = opener.mutate
  useEffect(() => {
    if (batch && opened.current !== batch && batch.split("/").length === 2) { opened.current = batch; openBatch(batch) }
  }, [batch, openBatch])
  const answers = useMutationOf((a: { question: string; answer: string }[]) => sendAnswers(view!.id, a))
  const confirm = useMutationOf((did: string) => decide(view!.id, did, { confirm: true }))
  const change = useMutationOf((a: { id: string; value: unknown }) => decide(view!.id, a.id, { change: a.value }))
  const all = useMutationOf(() => confirmAll(view!.id))
  const remove = useMutationOf((lid: string) => deleteLine(view!.id, lid))
  const rule = useMutationOf((r: string) => setMainRule(view!.id, r))
  const run = useMutationOf(() => startRun(view!.id), (r) => setView((v) => (v ? { ...v, frozen: true, run: r.run } : v)))
  const busy = [start, opener, answers, confirm, change, all, remove, rule, run].some((m) => m.isPending)

  const plan = view?.plan ?? null
  const result = usePlanResult(view?.id ?? null, view?.run != null)
  const byLine = new Map((result.data?.lines ?? []).map((l) => [l.id, l]))

  return (
    <div className="space-y-4">
      <PageHeader title="Plan" description="Ask a question, check the plan, confirm the decisions, run." />
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (question.trim()) { setView(null); start.mutate({ question, subs: parseSubQuestions(subText) }) } }}>
        <div className="flex gap-2">
          <Input aria-label="Question" placeholder="What do you want to know?" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <Button type="submit" disabled={busy || !question.trim()}>Plan</Button>
        </div>
        <SubQuestionsBox value={subText} onChange={setSubText} />
      </form>
      {view?.batch && <p className="text-sm text-muted-foreground">Batch plan {view.batch}: your changes are saved to its file.</p>}
      {view?.batch && (view.sub_questions ?? []).length > 0 && (
        <ul aria-label="Sub-questions" className="list-disc pl-5 text-sm">{(view.sub_questions ?? []).map((q) => <li key={q}>{q}</li>)}</ul>
      )}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {view && !plan && <Clarify view={view} busy={busy} onSend={(a) => answers.mutate(a)} />}

      {view && plan && (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">What would prove it?</h2>
            {plan.lines.map((l) => (
              <LineCard key={l.id} line={l} how={view.how[l.id]} result={byLine.get(l.id)} busy={busy || view.frozen} onRemove={view.frozen ? undefined : (id) => remove.mutate(id)} />
            ))}
            <MainRule rule={plan.main_rule} busy={busy || view.frozen} onChange={(r) => rule.mutate(r)} />
            <Button disabled={busy || view.frozen || !view.ready} onClick={() => run.mutate(undefined)}>Run</Button>
            {view.problems.length > 0 && (
              <ul role="alert" className="list-disc pl-5 text-sm text-destructive">{view.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            )}
            {!view.frozen && view.problems.length === 0 && !view.ready && <p className="text-xs text-muted-foreground">Confirm every decision to run.</p>}

            {view.run && (
              <section aria-label="Answer" className="space-y-2">
                <h2 className="text-lg font-semibold">Answer</h2>
                {result.isError && <p role="alert" className="text-sm text-destructive">{result.error instanceof Error ? result.error.message : "The result could not be read."}</p>}
                {(result.isPending || result.data?.status === "running") ? <p className="text-sm text-muted-foreground">Running…</p> : result.data && (
                  <>
                    <p className="text-sm">{result.data.answer.text}</p>
                    {(result.data.answer.missing ?? []).map((m) => <p key={m} className="text-sm font-medium text-destructive">{m}</p>)}
                    <Labels labels={result.data.labels ?? {}} lines={plan.lines} />
                    <Reruns reruns={result.data.reruns ?? []} />
                    <Links links={result.data.links ?? []} />
                  </>
                )}
              </section>
            )}
          </div>
          <DecisionsPanel decisions={plan.decisions} busy={busy || view.frozen}
            onConfirm={(id) => confirm.mutate(id)} onChange={(id, value) => change.mutate({ id, value })} onConfirmAll={() => all.mutate(undefined)} />
        </div>
      )}
    </div>
  )
}
