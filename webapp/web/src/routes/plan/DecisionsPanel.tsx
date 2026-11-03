/** The decisions panel: each choice the planner made with its reason, Confirm / Change, flagged ones highlighted
 * with the critic's reason, and "Confirm all". Unconfirmed choices say "made by LLM". */
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

import { MAIN_RULE_ID, parseValue, RULES, type PlanDecision } from "./api"

const LABELS: Record<PlanDecision["type"], string> = {
  must_match: "Must match",
  counts_as: "Counts as",
  threshold: "Threshold",
  include: "Include",
  main_rule: "Main answer rule",
}

const show = (value: unknown) => (typeof value === "string" ? value : JSON.stringify(value))


function DecisionRow({ d, busy, onConfirm, onChange }: {
  d: PlanDecision
  busy: boolean
  onConfirm: (id: string) => void
  onChange: (id: string, value: unknown) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(show(d.value))
  return (
    <li data-decision={d.id} data-flagged={d.flagged ? "true" : "false"}
      className={`space-y-1 rounded-md border p-3 ${d.flagged ? "border-amber-500 bg-amber-50 dark:bg-amber-950/30" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{d.id === MAIN_RULE_ID ? "Main answer rule" : LABELS[d.type]}</span>
        <span className="font-mono text-sm">{show(d.value)}</span>
        {d.confirmed_by ? <Badge variant="secondary">confirmed by {d.confirmed_by}</Badge> : <Badge variant="outline">made by LLM</Badge>}
      </div>
      <p className="text-xs text-muted-foreground">{d.reason}</p>
      {d.flagged && <p className="text-xs font-medium text-amber-800 dark:text-amber-300">Doubted: {d.flag_reason}</p>}
      {editing ? (
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); onChange(d.id, d.id === MAIN_RULE_ID ? draft : parseValue(draft)); setEditing(false) }}>
          {d.id === MAIN_RULE_ID ? (
            <select aria-label="Main answer rule" className="h-9 rounded-md border bg-background px-2 text-sm" value={draft} onChange={(e) => setDraft(e.target.value)}>
              {Object.entries(RULES).map(([name, text]) => <option key={name} value={name}>{name}: {text}</option>)}
            </select>
          ) : (
            <Input aria-label={`New value for ${LABELS[d.type]}`} value={draft} onChange={(e) => setDraft(e.target.value)} />
          )}
          <Button type="submit" size="sm" disabled={busy}>Save</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
        </form>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={busy || d.confirmed_by !== null} onClick={() => onConfirm(d.id)}>Confirm</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setEditing(true)}>Change</Button>
        </div>
      )}
    </li>
  )
}

export function DecisionsPanel({ decisions, busy = false, onConfirm, onChange, onConfirmAll }: {
  decisions: PlanDecision[]
  busy?: boolean
  onConfirm: (id: string) => void
  onChange: (id: string, value: unknown) => void
  onConfirmAll: () => void
}) {
  const open = decisions.filter((d) => d.confirmed_by === null).length
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-base">Decisions{open > 0 ? ` (${open} to confirm)` : ""}</CardTitle>
        <Button size="sm" disabled={busy || open === 0} onClick={onConfirmAll}>Confirm all</Button>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {decisions.map((d) => <DecisionRow key={`${d.id}:${show(d.value)}`} d={d} busy={busy} onConfirm={onConfirm} onChange={onChange} />)}
        </ul>
      </CardContent>
    </Card>
  )
}
