/**
 * Freeze with serious problems: each one needs a written reason from a person (at least 10 characters, as
 * evidence/propose/cards.py `waivers` requires). The reasons are written to decisions.yaml with the decisions.
 */
import { useState } from "react"

import type { CheckProblem } from "@/api/ev"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export const MIN_WAIVER_REASON = 10

export function WaiverDialog({ problems, open, onOpenChange, busy, onConfirm }: {
  problems: CheckProblem[]
  open: boolean
  onOpenChange: (open: boolean) => void
  busy: boolean
  onConfirm: (waivers: { check: string; reason: string }[]) => void
}) {
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const checks = [...new Set(problems.map((p) => p.check))]
  const short = (c: string) => (reasons[c] ?? "").trim().length < MIN_WAIVER_REASON
  const ok = checks.length > 0 && !checks.some(short)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Waive serious problems and freeze?</DialogTitle>
          <DialogDescription>
            A run of this protocol may fail or answer nothing because of these. Freezing needs a reason for each, in your name.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {checks.map((c) => {
            const id = `waiver-${c}`
            const typed = (reasons[c] ?? "").length > 0
            return (
              <div key={c} className="grid gap-1.5">
                <p className="text-sm"><span className="font-mono text-xs">{c}</span>: {problems.filter((p) => p.check === c).map((p) => p.message).join(" ")}</p>
                <Label htmlFor={id}>Reason for waiving {c}</Label>
                <Textarea id={id} className="min-h-16" value={reasons[c] ?? ""} onChange={(e) => setReasons((r) => ({ ...r, [c]: e.target.value }))}
                  aria-invalid={typed && short(c)} aria-describedby={`${id}-hint`} />
                <p id={`${id}-hint`} className={typed && short(c) ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
                  A reason of at least {MIN_WAIVER_REASON} characters: say why it is safe.
                </p>
              </div>
            )
          })}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Keep editing</Button>
          <Button disabled={!ok || busy} onClick={() => onConfirm(checks.map((c) => ({ check: c, reason: (reasons[c] ?? "").trim() })))}>Waive and freeze</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
