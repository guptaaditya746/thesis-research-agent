/**
 * The judge test: Aditya marks answers by hand without seeing the judge's marks or the system that answered.
 * Nothing here reads either (the API does not send them). A row with a `problem` is shown and cannot be opened.
 * An item judged again on another answer or sheet comes with a `note` and no earlier marks: it is marked afresh.
 * The ticks belong to what the server showed (`shown`): when the answer or the points under them change, the ticks
 * start empty, and a save names `shown` so the server refuses a mark made on something else.
 */
import { useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { useJudgeItem, useJudgeList, useSaveMark, type JudgeItem } from "./api"
import { messageOf } from "./messageOf"

export function JudgeTestTab() {
  const list = useJudgeList()
  const [open, setOpen] = useState<number | null>(null)
  if (list.error) return <Alert variant="destructive"><AlertDescription>{messageOf(list.error)}</AlertDescription></Alert>
  return (
    <div className="space-y-4">
      <ul className="space-y-1 text-sm">
        {(list.data ?? []).map((r) => (
          <li key={r.n} className="flex items-center gap-2">
            <span>{r.n + 1}.</span>
            {r.problem ? (
              <>
                <Button variant="link" size="sm" disabled>Row {r.n + 1}</Button>
                <span className="text-destructive">{r.problem}</span>
              </>
            ) : (
              <Button variant="link" size="sm" onClick={() => setOpen(r.n)}>{r.question_id} ({r.domain}, seed {r.seed})</Button>
            )}
            {r.done ? <span className="text-muted-foreground">done</span> : null}
          </li>
        ))}
      </ul>
      {open !== null ? <Item key={open} n={open} /> : null}
    </div>
  )
}

function Item({ n }: { n: number }) {
  const item = useJudgeItem(n)
  const save = useSaveMark(n)   // here, not in Marking: a refusal stays on screen when the item is loaded again
  if (item.error) return <Alert variant="destructive"><AlertDescription>{messageOf(item.error)}</AlertDescription></Alert>
  if (!item.data) return <p className="text-sm text-muted-foreground">Loading</p>
  return <Marking key={item.data.shown} item={item.data} save={save} />
}

type Faithful = "yes" | "no" | "skip"

function Marking({ item, save }: { item: JudgeItem; save: ReturnType<typeof useSaveMark> }) {
  const [met, setMet] = useState<Record<string, boolean>>(() => item.marked?.points ?? {})
  const [faithful, setFaithful] = useState<Faithful>(() => (item.marked?.faithful === true ? "yes" : item.marked?.faithful === false ? "no" : "skip"))
  const [saved, setSaved] = useState(false)
  const complete = item.points.every((p) => p.id in met)
  const options: [string, boolean][] = [["Met", true], ["Not met", false]]
  return (
    <Card role="region" aria-label="Judge-test item">
      <CardHeader><CardTitle className="text-base">{item.question_id} (seed {item.seed})</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {item.note ? <Alert><AlertDescription>Mark this item again: {item.note}.</AlertDescription></Alert> : null}
        {item.question ? <p className="font-medium">{item.question}</p> : null}
        <div>
          <p className="font-medium">Answer</p>
          <p className="whitespace-pre-wrap">{item.answer}</p>
        </div>
        <div>
          <p className="font-medium">Facts or passages the answer used</p>
          {item.facts_cut ? <p className="text-muted-foreground">Some were cut for length.</p> : null}
          <ol className="space-y-1">
            {item.facts.map((f) => <li key={f.n}>{f.n}. [{f.paper}] {f.quote}</li>)}
          </ol>
        </div>
        <div className="space-y-2">
          <p className="font-medium">Points</p>
          {item.points.map((p) => (
            <fieldset key={p.id} className="flex flex-wrap items-center gap-3">
              <legend className="sr-only">{p.id}</legend>
              <span className="flex-1">{p.text}</span>
              {options.map(([text, value]) => (
                <label key={text} className="flex items-center gap-1">
                  <input type="radio" name={`point-${p.id}`} checked={met[p.id] === value} onChange={() => { setSaved(false); setMet({ ...met, [p.id]: value }) }} />
                  {text}
                </label>
              ))}
            </fieldset>
          ))}
        </div>
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="font-medium">Uses its facts faithfully</legend>
          {(["yes", "no", "skip"] as const).map((v) => (
            <label key={v} className="flex items-center gap-1">
              <input type="radio" name="faithful" checked={faithful === v} onChange={() => { setSaved(false); setFaithful(v) }} />
              {v}
            </label>
          ))}
        </fieldset>
        <div className="space-y-2">
          <Button disabled={!complete || save.isPending}
            onClick={() => save.mutate({ points: met, faithful: faithful === "skip" ? null : faithful === "yes", shown: item.shown }, { onSuccess: () => setSaved(true) })}>Save</Button>
          {!complete ? <p className="text-muted-foreground">Mark every point first.</p> : null}
          {save.error ? <Alert variant="destructive"><AlertDescription>{messageOf(save.error)}</AlertDescription></Alert> : null}
          {saved ? <p role="status" className="text-muted-foreground">Saved.</p> : null}
        </div>
      </CardContent>
    </Card>
  )
}
