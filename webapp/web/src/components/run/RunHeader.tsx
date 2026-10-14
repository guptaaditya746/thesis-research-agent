/** The run page's head: identity, the stats row (exit, steps, tokens, time, claims, verify) and actions. */
import { FileJsonIcon, GitCompareArrowsIcon, Loader2Icon, MessageSquareIcon, TriangleAlertIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { RunConfig, RunDetail } from "@/api/types"
import { ConditionBadge, ExitBadge, LiveDot, ProvisionalBadge, StatusBadge, VerifyBadge } from "@/components/badges"
import { useChat } from "@/components/chat/context"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { dateTime, duration, int, tokens } from "@/lib/format"
import { ANSWER_FROM_LABEL, ATTACH_LABEL, splitRunId } from "@/lib/run"

export function RunHeader({ detail, config }: { detail: RunDetail; config: RunConfig }) {
  const { summary: s, verify } = detail
  const { setOpen } = useChat()
  const { batch, name } = splitRunId(s.run_id)
  return (
    <div className="space-y-4">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {s.live && <LiveDot label="the agent is writing this run" />}
            <span className="font-mono break-all">{name}</span>
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-2">
            {batch && <Badge variant="secondary" className="font-mono font-normal" title="batch">{batch}</Badge>}
            {s.qid && <Link to={`/questions/${s.qid}`} className="font-mono hover:underline">{s.qid}</Link>}
            <ConditionBadge condition={s.condition} />
            <span>seed {s.seed ?? "—"} · T {s.temperature ?? "—"} · {dateTime(s.created_at)}</span>
            {detail.concept && <span>· concept “{detail.concept.title}”</span>}
            {config.prompt?.version && <Badge variant="outline" className="font-mono font-normal">prompt {config.prompt.version}</Badge>}
            {s.concept_current === false && (
              <StatusBadge tone="warning" icon={<TriangleAlertIcon />} title="the question's pick changed after this run">replaced concept</StatusBadge>
            )}
            {s.score?.provisional && <ProvisionalBadge />}
            {s.post_processing && (
              <StatusBadge tone="neutral" icon={<Loader2Icon className="animate-spin motion-reduce:animate-none" />}>verifying and scoring</StatusBadge>
            )}
          </span>
        }
        actions={
          <>
            {s.qid && (
              <Button variant="outline" size="sm" asChild>
                <Link to={`/compare/${s.qid}?${s.condition === "claim_off" ? "off" : "on"}=${encodeURIComponent(s.run_id)}`}>
                  <GitCompareArrowsIcon data-icon="inline-start" />
                  Compare
                </Link>
              </Button>
            )}
            <ConfigDialog detail={detail} />
            <Button size="sm" onClick={() => setOpen(true)}>
              <MessageSquareIcon data-icon="inline-start" />
              Ask about this run
            </Button>
          </>
        }
      />
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Exit">
          <span className="flex flex-wrap items-center gap-1.5">
            <ExitBadge status={s.exit_status} live={s.live} />
            {s.answer_from && s.answer_from !== "final" && <span className="text-xs font-normal text-muted-foreground">{ANSWER_FROM_LABEL[s.answer_from]}</span>}
          </span>
        </Stat>
        <Stat label="Steps">
          {int(s.steps)}
          {config.budget?.steps ? <span className="text-muted-foreground"> / {int(config.budget.steps)}</span> : null}
        </Stat>
        <Stat label="Tokens">
          {tokens(s.tokens)}
          {config.budget?.tokens ? <span className="text-muted-foreground"> / {tokens(config.budget.tokens)}</span> : null}
          {s.tokens_without_attach != null && s.tokens_without_attach !== s.tokens && (
            <span className="block text-xs font-normal text-muted-foreground">{tokens(s.tokens_without_attach)} without attach</span>
          )}
        </Stat>
        <Stat label="Time">
          {duration(s.seconds)}
          {s.condition === "claim_off" && <span className="block text-xs font-normal text-muted-foreground">{ATTACH_LABEL[s.attach]}</span>}
        </Stat>
        <Stat label="Claims accepted / rejected">
          {s.claims_accepted} / {s.claims_rejected}
        </Stat>
        <Stat label="Verify">
          {verify && verify.errors.length > 0 ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="rounded-full focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none" aria-label={`verify failed: ${verify.errors.length} errors`}>
                  <VerifyBadge verify={s.verify} />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-sm">
                <ul className="list-disc pl-4">
                  {verify.errors.slice(0, 8).map((e) => <li key={e}>{e}</li>)}
                </ul>
              </TooltipContent>
            </Tooltip>
          ) : (
            <VerifyBadge verify={s.verify} />
          )}
        </Stat>
      </dl>
    </div>
  )
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg border bg-card px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-base font-medium tabular-nums">{children}</dd>
    </div>
  )
}

function ConfigDialog({ detail }: { detail: RunDetail }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <FileJsonIcon data-icon="inline-start" />
          Config
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>config.json and verify</DialogTitle>
          <DialogDescription>The run's settings as recorded, and `agent verify`'s statistics.</DialogDescription>
        </DialogHeader>
        <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
          {JSON.stringify({ config: detail.config, verify: detail.verify }, null, 2)}
        </pre>
      </DialogContent>
    </Dialog>
  )
}
