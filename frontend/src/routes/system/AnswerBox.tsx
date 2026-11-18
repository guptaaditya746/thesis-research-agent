/** Box 5: the answer. Its text, each line with its fact numbers as buttons (they open Pull out and mark the fact),
 * and, for a written answer that failed its checks, the problems. */
import type { SystemSteps } from "./api"
import { Box } from "./PickBox"
import { FactButtons } from "./RunBox"

export function AnswerBox({ open, steps, onSelect }: { open: boolean; steps: SystemSteps | undefined; onSelect: (n: number) => void }) {
  const answer = steps?.answer
  return (
    <Box title="5. Answer" open={open && answer !== undefined}>
      {answer && (
        <div role="group" aria-label="Answer box" className="space-y-3 text-sm">
          {answer.status === "failed" && (
            <p role="alert" className="text-destructive">{`The model's answer failed its checks: ${answer.problems.join("; ")}`}</p>
          )}
          <p>{answer.text}</p>
          <ul className="space-y-1">
            {answer.lines.map((l, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2"><span>{l.text}</span><FactButtons facts={l.facts} onSelect={onSelect} /></li>
            ))}
          </ul>
        </div>
      )}
    </Box>
  )
}
