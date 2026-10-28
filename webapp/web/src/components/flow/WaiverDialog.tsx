/**
 * Freeze with serious problems: each one needs a written reason from a person (at least 10 characters, as
 * evidence/propose/cards.py `waivers` requires). The reasons are written to decisions.yaml with the decisions.
 * The dialog says what is overridden (the card and the problem, in words), that waiving does not fix it, whose
 * name the reason is saved under, and that freezing is one-way.
 */
import { OctagonXIcon } from "lucide-react"
import { useState } from "react"

import type { CheckProblem } from "@/api/ev"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

export const MIN_WAIVER_REASON = 10

export function WaiverDialog({ problems, open, onOpenChange, busy, onConfirm, cardTitles = {}, user }: {
  problems: CheckProblem[]
  open: boolean
  onOpenChange: (open: boolean) => void
  busy: boolean
  onConfirm: (waivers: { check: string; reason: string }[]) => void
  /** card id → title, to name the card a problem belongs to */
  cardTitles?: Record<string, string>
  /** whose name the reasons are saved under ($WEBAPP_USER) */
  user?: string
}) {
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const checks = [...new Set(problems.map((p) => p.check))]
  const length = (c: string) => (reasons[c] ?? "").trim().length
  const short = (c: string) => length(c) < MIN_WAIVER_REASON
  const ok = checks.length > 0 && !checks.some(short)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Waive serious problems and freeze?</DialogTitle>
          <DialogDescription>
            A run of this protocol may fail or answer nothing because of {checks.length === 1 ? "this problem" : `these ${checks.length} problems`}.
            Waiving does not fix {checks.length === 1 ? "it" : "them"}: it records that you accept {checks.length === 1 ? "it" : "them"}, with a
            reason saved in decisions.yaml{user ? ` under your name (${user})` : ""}.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {checks.map((c) => {
            const id = `waiver-${c}`
            const typed = length(c) > 0
            const mine = problems.filter((p) => p.check === c)
            const cards = [...new Set(mine.map((p) => p.card).filter((x): x is string => !!x))]
            return (
              <div key={c} className="space-y-2 rounded-lg border border-destructive/40 p-3">
                <div className="flex gap-2 text-sm">
                  <OctagonXIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                  <div className="min-w-0 space-y-0.5">
                    {cards.length > 0 && <p className="font-medium">Card: {cards.map((k) => cardTitles[k] ?? k).join(", ")}</p>}
                    <p>{mine.map((p) => p.message).join(" ")}</p>
                    <p className="font-mono text-xs text-muted-foreground">check {c}</p>
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={id}>Reason for waiving {c}</Label>
                  <Textarea id={id} className="min-h-16" value={reasons[c] ?? ""} onChange={(e) => setReasons((r) => ({ ...r, [c]: e.target.value }))}
                    aria-invalid={typed && short(c)} aria-describedby={`${id}-hint`} />
                  <p id={`${id}-hint`} className={cn("flex justify-between gap-2 text-xs", typed && short(c) ? "text-destructive" : "text-muted-foreground")}>
                    <span>A reason of at least {MIN_WAIVER_REASON} characters: say why it is safe.</span>
                    <span className="shrink-0 tabular-nums" aria-hidden="true">{Math.min(length(c), MIN_WAIVER_REASON)}/{MIN_WAIVER_REASON}</span>
                  </p>
                </div>
              </div>
            )
          })}
          <p className="text-xs text-muted-foreground">
            Freezing then writes the protocol as revision 1. It is one-way: later changes go through{" "}
            <span className="font-mono">evidence propose amend</span> on the command line.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Keep editing</Button>
          <Button disabled={!ok || busy} onClick={() => onConfirm(checks.map((c) => ({ check: c, reason: (reasons[c] ?? "").trim() })))}>
            {busy && <Spinner data-icon="inline-start" aria-hidden="true" />}
            Waive and freeze
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
