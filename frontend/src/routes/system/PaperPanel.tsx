/** A paper's text with one fact's spans marked: opened from a fact of the Pull out row. */
import { PaperText } from "@/components/ev/PaperText"

import { usePaper, type StepFact } from "./api"

const MARK = "var(--color-chart-1, #2563eb)"

export function PaperPanel({ rid, fact }: { rid: string; fact: StepFact }) {
  const paper = usePaper(rid, fact.paper)
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{`Fact ${fact.n} in ${fact.paper}`}</p>
      {paper.isError && <p role="alert" className="text-sm text-destructive">The paper could not be read.</p>}
      {paper.data && (
        <PaperText label={`Text of ${fact.paper}`} segments={paper.data.segments} colorOf={(m) => (m === fact.item ? MARK : null)}
          selected={fact.item} className="max-h-[40vh]" />
      )}
    </div>
  )
}
