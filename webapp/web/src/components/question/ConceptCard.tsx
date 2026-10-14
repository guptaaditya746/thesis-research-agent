/** One concept brief (agent/schemas/concept.schema.json) as a card, with its pick action. */
import { CheckCircle2Icon } from "lucide-react"
import type { ReactNode } from "react"

import type { ConceptBrief, Pick as ConceptPick } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { measureText } from "@/lib/concept"
import { cn } from "@/lib/utils"

import { AnswerShapePreview } from "./AnswerShapePreview"

export function ConceptCard({ brief, choice, picked, action }: {
  brief: ConceptBrief
  /** 1-based number of the brief, as `agent concept pick` takes it */
  choice: number
  picked: ConceptPick | null | undefined
  action: ReactNode
}) {
  const isPicked = picked?.choice === choice
  return (
    <Card className={cn("h-full", isPicked && "ring-2 ring-status-good/60")} aria-label={`Brief ${choice}: ${brief.title}`}>
      <CardHeader>
        <CardDescription className="font-mono text-xs">brief {choice}{brief.id ? ` · ${brief.id}` : ""}</CardDescription>
        <CardTitle className="leading-snug">{brief.title}</CardTitle>
        {isPicked && (
          <CardAction>
            <Badge variant="outline" className="gap-1">
              <CheckCircle2Icon className="text-status-good" aria-hidden="true" />
              picked by {picked.picked_by}
            </Badge>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 text-sm">
        <p>{brief.definition}</p>
        <Section title="Measure">
          <p className="font-mono text-xs">{measureText(brief.measure)}</p>
        </Section>
        <Section title="Scope">
          <dl className="space-y-1">
            {Object.entries(brief.scope).map(([key, value]) => (
              <div key={key}>
                <dt className="inline font-medium">{key}: </dt>
                <dd className="inline text-muted-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        </Section>
        <Section title={`Answer shape: ${brief.answer_shape.kind}`}>
          <AnswerShapePreview shape={brief.answer_shape} />
        </Section>
        <Section title="Competency questions">
          <ol className="list-decimal space-y-1 pl-4 text-muted-foreground">
            {brief.competency_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
        </Section>
        {brief.needs && brief.needs.length > 0 && (
          <Section title="Needs">
            <ul className="list-disc space-y-1 pl-4 text-muted-foreground">
              {brief.needs.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </Section>
        )}
        {isPicked && picked.reason && (
          <p className="rounded-md bg-muted/50 p-2 text-xs text-muted-foreground">Reason: {picked.reason}</p>
        )}
      </CardContent>
      <CardFooter className="mt-auto">{action}</CardFooter>
    </Card>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  )
}
