/**
 * Home `/`: the supervisor's flow as the app's map (STATE.md §1, §4): question → protocol → corpus → run →
 * evidence graph and answer → scores A/B/C with the baselines beside the engine. Each step says what is on
 * disk and links to its page; the directories the viewer reads are listed, so a missing one is plain.
 */
import { ArrowRightIcon, BarChart3Icon, DatabaseIcon, FileCode2Icon, FlaskConicalIcon, NetworkIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { useCorpora, useEvConfig, useEvRuns, useProposals, useProtocols, useScores } from "@/api/ev"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

function Step({ n, title, icon, to, children, count }: { n: number; title: string; icon: ReactNode; to: string; children: ReactNode; count?: string }) {
  return (
    <Card className="relative">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs tabular-nums">{n}</span>
          <span className="[&>svg]:size-4" aria-hidden="true">{icon}</span>
          <Link to={to} className="hover:underline after:absolute after:inset-0">{title}</Link>
          {count && <Badge variant="secondary" className="ml-auto font-normal">{count}</Badge>}
        </CardTitle>
        <CardDescription>{children}</CardDescription>
      </CardHeader>
    </Card>
  )
}

export default function HomePage() {
  const config = useEvConfig()
  const protocols = useProtocols()
  const proposals = useProposals()
  const corpora = useCorpora()
  const runs = useEvRuns()
  const scores = useScores()
  const question = protocols.data?.find((p) => p.question)?.question
  const engine = runs.data?.filter((r) => r.kind === "engine").length
  const baselines = runs.data?.filter((r) => r.kind === "baseline").length
  const count = (n: number | undefined, what: string) => (n === undefined ? undefined : `${n} ${what}`)
  return (
    <div className="space-y-6">
      <PageHeader title="Evidence-level flow" description="Question → protocol → run → evidence graph → answer → scores A/B/C per level, the baselines beside the engine. Read-only: runs are made on the command line and Slurm (docs/slurm-evidence-runbook.md)." />
      {question && (
        <blockquote className="border-l-4 pl-4 text-lg font-medium text-balance">{question}</blockquote>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Step n={1} title="Protocol" icon={<FileCode2Icon />} to="/protocol" count={count(protocols.data?.length, "protocols")}>
          The executable protocol (version 2): evidence types, cascades, screen, the synthesis rules. {proposals.data?.length ? `${proposals.data.length} proposal(s) from the proposal flow.` : ""}
        </Step>
        <Step n={2} title="Corpora" icon={<DatabaseIcon />} to="/corpora" count={count(corpora.data?.length, "corpora")}>
          Synthetic papers written from structured ground truth, per difficulty level, with knobs and controlled variants.
        </Step>
        <Step n={3} title="Runs" icon={<FlaskConicalIcon />} to="/runs" count={engine === undefined ? undefined : `${engine} engine, ${baselines} baseline`}>
          The engine per paper: screen, extraction cascade or funnel (all / gaps), items with their spans, the answer.
        </Step>
        <Step n={4} title="Evidence graph and answer" icon={<NetworkIcon />} to="/runs">
          Open a run: its graph, the answer with supporting and contradicting studies, flags, and every call down to the agent's trace.
        </Step>
        <Step n={5} title="Scores" icon={<BarChart3Icon />} to="/scores" count={count(scores.data?.reports.length, "reports")}>
          A extraction, B integration, C synthesis per level with 95 % intervals; all against gaps, shift, benchmark records.
        </Step>
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="text-base text-muted-foreground">Earlier work</CardTitle>
            <CardDescription>
              The 12 questions, concept picks, the claim on/off study, gold review and chat (dropped 16 Oct as a study) stay in the
              repository. <Link to="/earlier" className="inline-flex items-center gap-1 underline">Open <ArrowRightIcon className="size-3" /></Link>
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
      {config.data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Directories</CardTitle>
            <CardDescription>{config.data.ev ? <>From <span className="font-mono">$EV</span> = <span className="font-mono">{config.data.ev}</span>.</> : "Set $EV (or each variable) when starting `webapp serve`."}</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-1 text-sm sm:grid-cols-2">
              {(["corpora", "runs", "scores", "proposals", "cache", "agent_work", "protocols"] as const).map((k) => {
                const root = config.data[k]
                return (
                  <li key={k} className="flex min-w-0 items-center gap-2">
                    <span className={root.exists ? "text-status-good" : "text-muted-foreground"} aria-hidden="true">●</span>
                    <span className="w-24 shrink-0 text-muted-foreground">{k.replace("_", " ")}</span>
                    <span className="truncate font-mono text-xs" title={root.path ?? undefined}>{root.path ?? "not configured"}</span>
                    {!root.exists && root.path && <span className="text-xs text-muted-foreground">(missing)</span>}
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
