/**
 * An answer fact as a badge: its id, an icon and colour for its support status, and a tooltip
 * with the triple and the status in words. A button: it opens the fact's claim walk.
 */
import { CheckCircle2Icon, CircleDotIcon, CircleHelpIcon, CircleSlashIcon, Loader2Icon, XCircleIcon } from "lucide-react"

import type { AnswerFact } from "@/api/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { FACT_STATUS_LABEL, type FactStatus } from "@/lib/facts"
import { cn } from "@/lib/utils"

const ICON = {
  supported: { icon: CheckCircle2Icon, className: "text-status-good" },
  partial: { icon: CircleDotIcon, className: "text-status-warning" },
  not_supported: { icon: XCircleIcon, className: "text-status-critical" },
  unsourced: { icon: CircleSlashIcon, className: "text-status-serious" },
  unjudged: { icon: CircleHelpIcon, className: "text-muted-foreground" },
} satisfies Record<FactStatus, { icon: typeof CheckCircle2Icon; className: string }>

export function FactStatusIcon({ status, loading, className }: { status: FactStatus; loading?: boolean; className?: string }) {
  if (loading) return <Loader2Icon className={cn("size-3.5 animate-spin text-muted-foreground motion-reduce:animate-none", className)} aria-hidden="true" />
  const { icon: Icon, className: tone } = ICON[status]
  return <Icon className={cn("size-3.5", tone, className)} aria-hidden="true" />
}

export function FactBadge({ fact, status, loading, onOpen }: {
  fact: AnswerFact
  status: FactStatus
  loading?: boolean
  onOpen: () => void
}) {
  const label = loading ? "checking" : FACT_STATUS_LABEL[status]
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onOpen}
          data-status={status}
          aria-label={`Fact ${fact.id}: ${label}. Open the claim walk.`}
          className="inline-flex h-6 items-center gap-1 rounded-full border bg-background px-2 font-mono text-xs transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <FactStatusIcon status={status} loading={loading} />
          {fact.id}
          <span className="sr-only">{label}</span>
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-medium">{label}</p>
        <p className="font-mono">
          ({fact.s}, {fact.p}, {String(fact.o)})
        </p>
        <p>
          {fact.claims.length} claim{fact.claims.length === 1 ? "" : "s"} · origin {fact.origin}
        </p>
      </TooltipContent>
    </Tooltip>
  )
}
