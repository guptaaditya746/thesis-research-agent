/**
 * Run `/runs/:runId` (plan "Frontend pages" 4): the stats header and six tabs (answer, graph,
 * timeline, claims, provenance, score). The tab is in the URL (?tab=), and every tab can open
 * the one claim walk sheet of the page through the walk context.
 */
import { SearchXIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router"

import { isNotFound } from "@/api/client"
import { useRun } from "@/api/hooks"
import { AnswerTab } from "@/components/run/AnswerTab"
import { ClaimsTab } from "@/components/run/ClaimsTab"
import { ClaimWalkSheet } from "@/components/run/ClaimWalkSheet"
import { GraphTab } from "@/components/run/GraphTab"
import { ProvenanceTab } from "@/components/run/ProvenanceTab"
import { RunHeader } from "@/components/run/RunHeader"
import { ScoreTab } from "@/components/run/ScoreTab"
import { TimelineTab } from "@/components/run/TimelineTab"
import { WalkContext, type WalkTarget } from "@/components/run/walk-context"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { runConfig } from "@/lib/run"

const TABS = [
  { value: "answer", label: "Answer" },
  { value: "graph", label: "Graph" },
  { value: "timeline", label: "Timeline" },
  { value: "claims", label: "Claims" },
  { value: "provenance", label: "Provenance" },
  { value: "score", label: "Score" },
] as const

export default function RunPage() {
  const { runId = "" } = useParams()
  const run = useRun(runId)
  const [params, setParams] = useSearchParams()
  const tab = TABS.some((t) => t.value === params.get("tab")) ? params.get("tab")! : "answer"
  // The open walk belongs to one run: navigating to another run closes it.
  const [walkState, setWalkState] = useState<{ runId: string; target: WalkTarget | null }>({ runId, target: null })
  const walk = walkState.runId === runId ? walkState.target : null
  const walkApi = useMemo(() => ({ runId, open: (target: WalkTarget) => setWalkState({ runId, target }) }), [runId])
  const config = useMemo(() => runConfig(run.data?.config), [run.data?.config])

  if (run.isError) {
    return isNotFound(run.error) ? (
      <EmptyState icon={<SearchXIcon />} title={`No run ${runId}`} description="There is no such run directory under the runs root.">
        <Button asChild variant="outline"><Link to="/runs">All runs</Link></Button>
      </EmptyState>
    ) : (
      <ErrorState error={run.error} onRetry={() => void run.refetch()} />
    )
  }
  if (run.isPending) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading the run">
        <Skeleton className="h-8 w-80 max-w-full" />
        <Skeleton className="h-16 w-full" />
        <CardsSkeleton count={2} />
      </div>
    )
  }

  const detail = run.data
  const live = detail.summary.live
  return (
    <WalkContext.Provider value={walkApi}>
      <div className="space-y-4" key={runId}>
        <RunHeader detail={detail} config={config} />
        <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })}>
          <div className="overflow-x-auto">
            <TabsList>
              {TABS.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
              ))}
            </TabsList>
          </div>
          <TabsContent value="answer" className="pt-2">
            <AnswerTab runId={runId} answer={detail.answer} concept={detail.concept} summary={detail.summary} />
          </TabsContent>
          <TabsContent value="graph" className="pt-2">
            <GraphTab runId={runId} answer={detail.answer} />
          </TabsContent>
          <TabsContent value="timeline" className="pt-2">
            <TimelineTab runId={runId} live={live} budget={config.budget} />
          </TabsContent>
          <TabsContent value="claims" className="pt-2">
            <ClaimsTab runId={runId} answer={detail.answer} live={live} />
          </TabsContent>
          <TabsContent value="provenance" className="pt-2">
            <ProvenanceTab runId={runId} />
          </TabsContent>
          <TabsContent value="score" className="pt-2">
            <ScoreTab runId={runId} />
          </TabsContent>
        </Tabs>
        <ClaimWalkSheet runId={runId} target={walk} onClose={() => setWalkState({ runId, target: null })} />
      </div>
    </WalkContext.Provider>
  )
}
