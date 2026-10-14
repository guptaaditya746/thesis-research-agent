/**
 * Question `/questions/:qid` (plan "Frontend pages" 2): the concept briefs side by side, each
 * with its answer shape as a template, the pick (who picked, why) and the propose job.
 */
import { GitCompareArrowsIcon, ListChecksIcon, SearchXIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { isNotFound } from "@/api/client"
import { useQuestion } from "@/api/hooks"
import { ConceptBadge, GoldBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ConceptCard } from "@/components/question/ConceptCard"
import { PickDialog, ProposeDialog } from "@/components/question/ConceptDialogs"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function QuestionPage() {
  const { qid = "" } = useParams()
  const question = useQuestion(qid)

  if (question.isError) {
    return isNotFound(question.error) ? (
      <EmptyState icon={<SearchXIcon />} title={`No question ${qid}`} description="The question list (questions/questions.json) has no such id.">
        <Button asChild variant="outline"><Link to="/">Back to the overview</Link></Button>
      </EmptyState>
    ) : (
      <ErrorState error={question.error} onRetry={() => void question.refetch()} />
    )
  }

  const q = question.data
  return (
    <div className="space-y-6">
      <PageHeader
        title={q ? q.question : <Skeleton className="h-7 w-96 max-w-full" />}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="font-mono">{qid}</Badge>
            {q && <Badge variant="outline" className="font-normal">{q.category.replace("_", " ")}</Badge>}
            {q && <ConceptBadge status={q.concept.status} pickedBy={q.concept.picked_by} />}
            {q && <>gold <GoldBadge status={q.gold.status} /></>}
            {q?.source && <span className="text-xs">from {q.source}</span>}
          </span>
        }
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={`/runs?qid=${qid}`}>
                <ListChecksIcon data-icon="inline-start" />
                Runs{q ? ` (${q.runs.claim_on + q.runs.claim_off})` : ""}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to={`/compare/${qid}`}>
                <GitCompareArrowsIcon data-icon="inline-start" />
                Compare
              </Link>
            </Button>
            {q && <ProposeDialog qid={qid} hasBriefs={q.briefs.length > 0} />}
          </>
        }
      />
      {!q ? (
        <CardsSkeleton />
      ) : q.briefs.length === 0 ? (
        <EmptyState
          title="No concept briefs yet"
          description="Propose briefs: the model reads only the question and returns one to five ways to make it measurable."
        >
          <ProposeDialog qid={qid} hasBriefs={false} />
        </EmptyState>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {q.picked
              ? `Brief ${q.picked.choice} is picked (by ${q.picked.picked_by}). Picking another one changes the concept of new runs and of the gold key.`
              : "No brief is picked yet. Compare the briefs and pick the one that makes the question answerable."}
          </p>
          <div className="grid items-stretch gap-4 md:grid-cols-2 2xl:grid-cols-3" role="list" aria-label="Concept briefs">
            {q.briefs.map((brief, index) => (
              <div role="listitem" key={brief.id ?? index}>
                <ConceptCard
                  brief={brief}
                  choice={index + 1}
                  picked={q.picked}
                  action={<PickDialog qid={qid} choice={index + 1} title={brief.title} isPicked={q.picked?.choice === index + 1} />}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
