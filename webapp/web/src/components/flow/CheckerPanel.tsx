/**
 * The live checker beside the cards (POST /proposals/{name}/check, no model call): what is wrong with the draft
 * as the cards stand now. Serious problems would make a run fail or answer nothing: freeze refuses them unless a
 * person waives them with a reason. Advisory ones are only worth a look.
 */
import type { CheckProblem } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"

function Problems({ problems, waived }: { problems: CheckProblem[]; waived: Record<string, string> }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {problems.map((p) => (
        <li key={`${p.check}-${p.card}-${p.message}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-mono text-xs">{p.check}</span>
          <span>{p.message}</span>
          {p.card && <Badge variant="outline">card {p.card}</Badge>}
          {waived[p.check] && <Badge variant="secondary" title={waived[p.check]}>waived</Badge>}
        </li>
      ))}
    </ul>
  )
}

export function CheckerPanel({ problems, pending, failed, waived }: { problems: CheckProblem[] | undefined; pending: boolean; failed: boolean; waived: Record<string, string> }) {
  const serious = (problems ?? []).filter((p) => p.severity === "serious")
  const advisory = (problems ?? []).filter((p) => p.severity === "advisory")
  return (
    <section aria-label="Checker" className="space-y-3 rounded-lg border p-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        Checker {pending && <Spinner className="size-3.5" aria-label="Checking" />}
      </h3>
      {failed && <p className="text-xs text-muted-foreground">The checker did not answer; freeze still checks the decisions.</p>}
      {problems && problems.length === 0 && <p className="text-sm text-muted-foreground">No problems found.</p>}
      {serious.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-destructive">must be fixed or waived</p>
          <Problems problems={serious} waived={waived} />
        </div>
      )}
      {advisory.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">worth a look</p>
          <Problems problems={advisory} waived={waived} />
        </div>
      )}
    </section>
  )
}
