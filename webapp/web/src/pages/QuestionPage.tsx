/**
 * Question `/earlier/questions/:qid` (plan "Frontend pages" 2): the concept briefs side by side, each
 * with its answer shape as a template, the pick (who picked, why) and the propose job; the gold
 * build of the question starts here too once a brief is picked.
 */
import { AwardIcon, GitCompareArrowsIcon, ListChecksIcon, SearchXIcon } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router"

import { isNotFound } from "@/api/client"
import { isActiveJob, useBuildGold, useJobs, useQuestion } from "@/api/hooks"
import { ConceptBadge, GoldBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { ConceptCard } from "@/components/question/ConceptCard"
import { PickDialog, ProposeDialog } from "@/components/question/ConceptDialogs"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { buildStopped, stageText } from "@/lib/gold"
import { announceError, announceJob } from "@/lib/toasts"

export default function QuestionPage() {
  const { qid = "" } = useParams()
  const question = useQuestion(qid)
  const jobs = useJobs()
  const buildGold = useBuildGold()
  const navigate = useNavigate()

  if (question.isError) {
    return isNotFound(question.error) ? (
      <EmptyState icon={<SearchXIcon />} title={`No question ${qid}`} description="The question list (questions/questions.json) has no such id.">
        <Button asChild variant="outline"><Link to="/earlier">Back to the overview</Link></Button>
      </EmptyState>
    ) : (
      <ErrorState error={question.error} onRetry={() => void question.refetch()} />
    )
  }

  const q = question.data
  const briefs = q?.briefs ?? []
  const proposing = jobs.data?.find((j) => j.kind === "concepts" && j.qid === qid && isActiveJob(j))
  const goldJob = jobs.data?.find((j) => j.kind === "gold" && j.qid === qid && isActiveJob(j))
  const runsOnCurrent = (q?.runs.claim_on ?? 0) + (q?.runs.claim_off ?? 0)
  const locked = q && q.gold.status !== "none" ? `The gold build for ${qid} has started on the current pick; it can no longer change.` : null

  const startGold = () =>
    buildGold.mutate(qid, {
      onSuccess: (job) => announceJob(job, navigate, `Building the gold standard of ${qid}`),
      onError: (error) => announceError("Could not start the gold build", error),
    })

  return (
    <div className="space-y-6">
      <PageHeader
        title={q ? q.question : <Skeleton className="h-7 w-96 max-w-full" />}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="font-mono">{qid}</Badge>
            {q?.category && <Badge variant="outline" className="font-normal">{q.category.replace("_", " ")}</Badge>}
            {q && <ConceptBadge status={q.concept.status} pickedBy={q.concept.picked_by} />}
            {q && <>gold <GoldBadge status={q.gold.status} /></>}
            {q && !goldJob && buildStopped(q.gold) && <span className="text-xs">({stageText(q.gold)})</span>}
            {q?.source && <span className="text-xs">from {q.source}</span>}
          </span>
        }
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={`/earlier/runs?qid=${qid}`}>
                <ListChecksIcon data-icon="inline-start" />
                Runs{q ? ` (${runsOnCurrent})` : ""}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to={`/earlier/compare/${qid}`}>
                <GitCompareArrowsIcon data-icon="inline-start" />
                Compare
              </Link>
            </Button>
            {q?.picked && (q.gold.status === "none" || buildStopped(q.gold)) && (
              <Button variant="outline" onClick={startGold} disabled={buildGold.isPending || !!goldJob}>
                {buildGold.isPending || goldJob ? <Spinner data-icon="inline-start" /> : <AwardIcon data-icon="inline-start" />}
                {goldJob ? "Gold build running" : q.gold.status === "none" ? "Build the gold standard" : "Run the gold build again"}
              </Button>
            )}
          </>
        }
      />
      {!q ? (
        <CardsSkeleton />
      ) : briefs.length === 0 ? (
        <EmptyState
          title="No concept briefs yet"
          description={
            proposing
              ? `Job ${proposing.id} is proposing briefs; they appear here when it finishes.`
              : "Propose briefs: the model reads only the question and returns one to five ways to make it measurable."
          }
        >
          {proposing ? (
            <Button variant="outline" asChild>
              <Link to={`/earlier/jobs/${proposing.id}`}><Spinner data-icon="inline-start" /> Follow the job</Link>
            </Button>
          ) : (
            <ProposeDialog qid={qid} />
          )}
        </EmptyState>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {q.picked
              ? `Brief ${q.picked.choice} is picked (by ${q.picked.picked_by}). ${locked ?? "Picking another one changes the concept of new runs and of the gold standard."}`
              : "No brief is picked yet. Compare the briefs and pick the one that makes the question answerable."}
          </p>
          <div className="grid items-stretch gap-4 md:grid-cols-2 2xl:grid-cols-3" role="list" aria-label="Concept briefs">
            {briefs.map((brief, index) => (
              <div role="listitem" key={brief.id ?? index}>
                <ConceptCard
                  brief={brief}
                  choice={index + 1}
                  picked={q.picked}
                  action={
                    <PickDialog
                      qid={qid}
                      choice={index + 1}
                      title={brief.title}
                      isPicked={q.picked?.choice === index + 1}
                      changes={!!q.picked && q.picked.choice !== index + 1}
                      runsOnCurrent={runsOnCurrent}
                      locked={locked}
                    />
                  }
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
