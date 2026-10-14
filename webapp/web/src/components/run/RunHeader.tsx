/** The run page's head: identity, the stats row (exit, steps, tokens, time, claims, verify) and actions. */
import { FileJsonIcon, GitCompareArrowsIcon, MessageSquareIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { RunDetail } from "@/api/types"
import { ConditionBadge, ExitBadge, LiveDot, VerifyBadge } from "@/components/badges"
import { useChat } from "@/components/chat/context"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { dateTime, duration, int, tokens } from "@/lib/format"

export function RunHeader({ detail }: { detail: RunDetail }) {
  const { summary: s, config, verify } = detail
  const { setOpen } = useChat()
  return (
    <div className="space-y-4">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {s.live && <LiveDot />}
            <span className="font-mono">{s.run_id}</span>
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Link to={`/questions/${s.qid}`} className="font-mono hover:underline">{s.qid}</Link>
            <ConditionBadge condition={s.condition} />
            <span>seed {s.seed} · T {s.temperature} · {dateTime(s.created_at)}</span>
            <span>· concept “{detail.concept.title}”</span>
            {config.prompt && <Badge variant="outline" className="font-mono font-normal">prompt {config.prompt.version}</Badge>}
          </span>
        }
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link to={`/compare/${s.qid}`}>
                <GitCompareArrowsIcon data-icon="inline-start" />
                Compare
              </Link>
            </Button>
            <ConfigDialog detail={detail} />
            <Button size="sm" onClick={() => setOpen(true)}>
              <MessageSquareIcon data-icon="inline-start" />
              Ask about this run
            </Button>
          </>
        }
      />
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Exit"><ExitBadge status={s.exit_status} live={s.live} /></Stat>
        <Stat label="Steps">
          {int(s.steps)}
          {config.budget && <span className="text-muted-foreground"> / {int(config.budget.steps)}</span>}
        </Stat>
        <Stat label="Tokens">
          {tokens(s.tokens)}
          {config.budget && <span className="text-muted-foreground"> / {tokens(config.budget.tokens)}</span>}
        </Stat>
        <Stat label="Time">{duration(s.seconds)}</Stat>
        <Stat label="Claims accepted / rejected">
          {s.claims_accepted} / {s.claims_rejected}
        </Stat>
        <Stat label="Verify">
          {verify.errors.length > 0 ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="rounded-full focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
                  <VerifyBadge verify={s.verify} />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-sm">
                <ul className="list-disc pl-4">
                  {verify.errors.map((e) => <li key={e}>{e}</li>)}
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
    <div className="rounded-lg border bg-card px-3 py-2">
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
