/**
 * An answer fact as a badge: its id, an icon and colour for its support status, and a tooltip
 * with the triple and the status in words. A button: it opens the fact's claim walk.
 */
import { CheckCircle2Icon, CircleDotIcon, CircleHelpIcon, CircleSlashIcon, HourglassIcon, XCircleIcon } from "lucide-react"

import type { Fact } from "@/api/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { FACT_STATUS_LABEL, term, type FactStatus } from "@/lib/facts"
import { cn } from "@/lib/utils"

const ICON = {
  supported: { icon: CheckCircle2Icon, className: "text-status-good" },
  partial: { icon: CircleDotIcon, className: "text-status-warning" },
  not_supported: { icon: XCircleIcon, className: "text-status-critical" },
  unsourced: { icon: CircleSlashIcon, className: "text-status-serious" },
  pending: { icon: HourglassIcon, className: "text-muted-foreground" },
  unjudged: { icon: CircleHelpIcon, className: "text-muted-foreground" },
} satisfies Record<FactStatus, { icon: typeof CheckCircle2Icon; className: string }>

export function FactStatusIcon({ status, className }: { status: FactStatus; className?: string }) {
  const { icon: Icon, className: tone } = ICON[status]
  return <Icon className={cn("size-3.5 shrink-0", tone, className)} aria-hidden="true" />
}

export function FactBadge({ fact, status, onOpen }: { fact: Fact; status: FactStatus; onOpen: () => void }) {
  const label = FACT_STATUS_LABEL[status]
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
          <FactStatusIcon status={status} />
          {fact.id}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-medium">{label}</p>
        <p className="font-mono">
          ({term(fact.s)}, {term(fact.p)}, {term(fact.o)})
        </p>
        <p>
          {fact.claims.length} claim{fact.claims.length === 1 ? "" : "s"} · origin {fact.origin}
        </p>
      </TooltipContent>
    </Tooltip>
  )
}
