/**
 * The frame of the earlier work's pages (`/earlier/...`): the 12 questions, concept picks, the claim on/off
 * runs and their scoring, gold review, jobs and the chat. They stay in the repository and keep working, but
 * they are not the thesis's flow since 16 Oct (docs/STATE.md §4, docs/earlier-work.md); the note says so on
 * every one of them. A note, not an alert: the pages' own alerts are their errors.
 */
import { ArchiveIcon } from "lucide-react"
import { Link, Outlet } from "react-router"

export function EarlierFrame() {
  return (
    <div className="space-y-4">
      <aside aria-label="Earlier work" className="flex gap-3 rounded-lg border bg-muted/40 px-4 py-3 text-sm">
        <ArchiveIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">Earlier work</p>
          <p className="text-muted-foreground">
            The research agent's claim on/off study (12 questions, concept picks, gold review), dropped as a study on 16 Oct; the agent is now
            one extractor and a baseline. Kept as it was (docs/earlier-work.md). <Link to="/" className="underline">Back to the evidence-level flow</Link>.
          </p>
        </div>
      </aside>
      <Outlet />
    </div>
  )
}
