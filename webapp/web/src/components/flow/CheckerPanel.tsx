/**
 * The live checker beside the cards (POST /proposals/{name}/check, no model call): what is wrong with the draft
 * as the cards stand now. Serious problems would make a run fail or answer nothing: freeze refuses them unless a
 * person waives them with a reason. Advisory ones are only worth a look. A problem that belongs to a card links to
 * it (`onShowCard`), so the person goes from the problem to the field that fixes it.
 */
import { CircleCheckIcon, InfoIcon, OctagonXIcon } from "lucide-react"

import type { CheckProblem } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

function Problems({ problems, waived, cardTitles, onShowCard, serious }: {
  problems: CheckProblem[]
  waived: Record<string, string>
  cardTitles: Record<string, string>
  onShowCard?: (card: string) => void
  serious: boolean
}) {
  const Icon = serious ? OctagonXIcon : InfoIcon
  return (
    <ul className="space-y-2 text-sm">
      {problems.map((p) => (
        <li key={`${p.check}-${p.card}-${p.message}`} className="flex gap-2">
          <Icon className={serious ? "mt-0.5 size-4 shrink-0 text-destructive" : "mt-0.5 size-4 shrink-0 text-muted-foreground"} aria-hidden="true" />
          <div className="min-w-0 space-y-1">
            <p>{p.message}</p>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {p.card && (onShowCard ? (
                <Button type="button" variant="link" size="xs" className="h-6 px-0" onClick={() => onShowCard(p.card!)}>
                  Go to card: {cardTitles[p.card] ?? p.card}
                </Button>
              ) : <Badge variant="outline">card {cardTitles[p.card] ?? p.card}</Badge>)}
              <span className="font-mono text-xs text-muted-foreground">{p.check}</span>
              {waived[p.check] && <Badge variant="secondary" title={waived[p.check]}>waived</Badge>}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function CheckerPanel({ problems, pending, failed, waived, cardTitles = {}, onShowCard }: {
  problems: CheckProblem[] | undefined
  pending: boolean
  failed: boolean
  waived: Record<string, string>
  /** card id → its title, for the links to the cards */
  cardTitles?: Record<string, string>
  /** scroll to the card and focus its first field */
  onShowCard?: (card: string) => void
}) {
  const serious = (problems ?? []).filter((p) => p.severity === "serious")
  const advisory = (problems ?? []).filter((p) => p.severity === "advisory")
  const open = serious.filter((p) => !waived[p.check]).length
  return (
    <section aria-label="Checker" className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Checker</h3>
        {pending && <Spinner className="size-3.5 text-muted-foreground" aria-label="Checking" />}
      </div>
      <p className="text-xs text-muted-foreground">Re-checks the draft each time you stop typing. Only serious problems stop the freeze.</p>
      {/* one polite line for a screen reader: the count changes as the cards change */}
      {problems && (
        <p role="status" className="text-sm font-medium">
          {problems.length === 0 ? (
            <span className="flex items-center gap-1.5"><CircleCheckIcon className="size-4 text-status-good" aria-hidden="true" />No problems found.</span>
          ) : `${serious.length} serious${open < serious.length ? ` (${serious.length - open} waived)` : ""}, ${advisory.length} to look at.`}
        </p>
      )}
      {failed && <p className="text-xs text-muted-foreground">The checker did not answer; freeze still checks the decisions.</p>}
      {!problems && !failed && <p className="text-sm text-muted-foreground" role="status">Checking the cards…</p>}
      {serious.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs font-semibold text-destructive">must be fixed or waived</p>
          <Problems problems={serious} waived={waived} cardTitles={cardTitles} onShowCard={onShowCard} serious />
        </div>
      )}
      {advisory.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs font-semibold text-muted-foreground">worth a look</p>
          <Problems problems={advisory} waived={waived} cardTitles={cardTitles} onShowCard={onShowCard} serious={false} />
        </div>
      )}
    </section>
  )
}
