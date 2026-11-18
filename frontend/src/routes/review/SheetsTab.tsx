/**
 * The answer-sheet queue and the editor of one sheet. The points are editable text with their fact ids as
 * removable chips; a stale sheet is saved as a new (unchecked) sheet, a missing one is written. The editor keeps
 * its text when a save is refused. A save names the sheet the points were loaded from (`shown`); when the sheet
 * changes on disk while the editor is open, the text is kept, Save is off and a button loads the new sheet.
 */
import { useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

import { useQueue, useSaveSheet, useSheet, type PointIn, type SheetView } from "./api"
import { messageOf } from "./messageOf"

const rank = (m: string | null) => (m === "full" ? 0 : m === "sample" ? 1 : 2)

export function SheetsTab({ domain }: { domain: string }) {
  const queue = useQueue(domain)
  const [first, setFirst] = useState(true)
  const [open, setOpen] = useState<{ seed: number; qid: string } | null>(null)
  if (queue.error) return <Alert variant="destructive"><AlertDescription>{messageOf(queue.error)}</AlertDescription></Alert>
  const rows = [...(queue.data ?? [])]
  if (first) rows.sort((a, b) => rank(a.must_check) - rank(b.must_check) || a.seed - b.seed || a.question_id.localeCompare(b.question_id))
  return (
    <div className="space-y-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th className="py-1">Seed</th><th>Question</th><th>Status</th>
            <th><button type="button" className="underline" aria-pressed={first} onClick={() => setFirst(!first)}>Must check</button></th>
            <th>Stale</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.seed}/${r.question_id}`} className="border-t">
              <td className="py-1">{r.seed}</td>
              <td><Button variant="link" size="sm" onClick={() => setOpen({ seed: r.seed, qid: r.question_id })}>{r.question_id}</Button></td>
              <td>{r.status}</td>
              <td>{r.must_check ?? ""}</td>
              <td>{r.stale ? "stale" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {open ? <SheetEditor key={`${open.seed}/${open.qid}`} domain={domain} seed={open.seed} qid={open.qid} /> : null}
    </div>
  )
}

function SheetEditor({ domain, seed, qid }: { domain: string; seed: number; qid: string }) {
  const sheet = useSheet(domain, seed, qid)
  if (sheet.error) return <Alert variant="destructive"><AlertDescription>{messageOf(sheet.error)}</AlertDescription></Alert>
  if (!sheet.data) return <p className="text-sm text-muted-foreground">Loading</p>
  return <Editor domain={domain} seed={seed} qid={qid} view={sheet.data} />
}

function Editor({ domain, seed, qid, view }: { domain: string; seed: number; qid: string; view: SheetView }) {
  const save = useSaveSheet(domain, seed, qid)
  const loaded = (): PointIn[] => (view.sheet?.points ?? []).map((p) => ({ text: p.text, facts: [...p.facts] }))
  const [points, setPoints] = useState<PointIn[]>(loaded)
  const [base, setBase] = useState<string | null>(view.shown)   // the sheet the points were loaded from, or saved as
  const [saved, setSaved] = useState(false)
  const moved = view.shown !== base
  const set = (i: number, p: PointIn) => { setSaved(false); setPoints(points.map((q, j) => (j === i ? p : q))) }
  const label = view.stale ? "Save as a new sheet" : view.sheet === null ? "Write and mark checked" : "Save and mark checked"
  const scope = view.scope
  const about = [...scope.arms, ...scope.conditions, ...scope.settings].join(", ")
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{qid} (seed {seed})</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {moved ? (
          <Alert>
            <AlertDescription>
              This sheet changed on disk after you opened it. Your text is kept and Save is off, because saving would replace the newer sheet.{" "}
              <Button size="sm" variant="outline" onClick={() => { setPoints(loaded()); setBase(view.shown); setSaved(false) }}>Load the sheet as it is now</Button>
            </AlertDescription>
          </Alert>
        ) : null}
        {view.stale ? <Alert><AlertDescription>This sheet is stale: {view.stale}. Saving makes a new sheet; save it again to check it.</AlertDescription></Alert> : null}
        <p className="font-medium">{view.question}</p>
        {view.sub_questions.length > 0 ? (
          <div>
            <p className="text-muted-foreground">Sub-questions (for planning only; not scored)</p>
            <ul className="list-disc pl-5">{view.sub_questions.map((s) => <li key={s}>{s}</li>)}</ul>
          </div>
        ) : null}
        <p>{`about: ${about}; measures: ${scope.measures.length ? scope.measures.join(", ") : "all"}`}</p>
        <div>
          <p className="font-medium">Facts</p>
          <ul>{view.facts.map((f) => <li key={f.id}><code className="text-xs">{f.id}</code> {f.text}</li>)}</ul>
        </div>
        {view.sheet?.warnings.length ? <Alert><AlertDescription>{view.sheet.warnings.join("; ")}</AlertDescription></Alert> : null}
        <div className="space-y-3">
          <p className="font-medium">Points</p>
          {points.map((p, i) => (
            <div key={i} className="space-y-1 rounded-md border p-2">
              <Textarea aria-label={`Point ${i + 1}`} value={p.text} onChange={(e) => set(i, { ...p, text: e.target.value })} />
              <div className="flex flex-wrap items-center gap-1">
                {p.facts.map((f) => (
                  <Badge key={f} variant="secondary" className="gap-1">
                    {f}
                    <button type="button" aria-label={`Remove fact ${f} from point ${i + 1}`} onClick={() => set(i, { ...p, facts: p.facts.filter((x) => x !== f) })}>x</button>
                  </Badge>
                ))}
                <select aria-label={`Add a fact to point ${i + 1}`} className="h-8 rounded-md border bg-background px-1 text-xs" value=""
                  onChange={(e) => { if (e.target.value) set(i, { ...p, facts: [...p.facts, e.target.value] }) }}>
                  <option value="">Add a fact</option>
                  {view.facts.filter((f) => !p.facts.includes(f.id)).map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
                </select>
                <Button size="sm" variant="ghost" onClick={() => { setSaved(false); setPoints(points.filter((_, j) => j !== i)) }}>Remove point {i + 1}</Button>
              </div>
            </div>
          ))}
          <Button size="sm" variant="outline" onClick={() => { setSaved(false); setPoints([...points, { text: "", facts: [] }]) }}>Add point</Button>
        </div>
        <div className="space-y-2">
          <Button disabled={save.isPending || moved} onClick={() => save.mutate({ points, shown: base }, { onSuccess: (r) => { setBase(r.shown); setSaved(true) } })}>{label}</Button>
          {save.error ? <Alert variant="destructive"><AlertDescription>{messageOf(save.error)}</AlertDescription></Alert> : null}
          {saved ? <p role="status" className="text-muted-foreground">Saved.</p> : null}
        </div>
      </CardContent>
    </Card>
  )
}
