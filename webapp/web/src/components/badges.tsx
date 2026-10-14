/**
 * Status badges. Colour never carries meaning alone: every status has an icon and a label;
 * the condition badge carries its series colour as a dot beside the text (dataviz rules: text
 * stays in text colours, the mark carries identity).
 */
import {
  CheckCircle2Icon,
  CircleDashedIcon,
  CircleDotIcon,
  CircleHelpIcon,
  CircleSlashIcon,
  ClockIcon,
  HammerIcon,
  Loader2Icon,
  OctagonXIcon,
  PencilLineIcon,
  ShieldCheckIcon,
  TriangleAlertIcon,
} from "lucide-react"
import type { ReactNode } from "react"

import type { Condition, ConceptStatus, ExitStatus, GoldStatus, JobState, PickedBy, VerifyState } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { CONDITION_LABEL } from "@/lib/format"
import { cn } from "@/lib/utils"

type Tone = "good" | "warning" | "serious" | "critical" | "neutral"

const ICON_TONE: Record<Tone, string> = {
  good: "text-status-good",
  warning: "text-status-warning",
  serious: "text-status-serious",
  critical: "text-status-critical",
  neutral: "text-muted-foreground",
}

export function StatusBadge({ tone, icon, children, title }: { tone: Tone; icon: ReactNode; children: ReactNode; title?: string }) {
  return (
    <Badge variant="outline" title={title} className="gap-1 font-normal">
      <span className={cn("inline-flex [&>svg]:size-3", ICON_TONE[tone])} aria-hidden="true">
        {icon}
      </span>
      {children}
    </Badge>
  )
}

const CONDITION_COLOR: Record<Condition, string> = { claim_on: "var(--chart-1)", claim_off: "var(--chart-2)" }

export function ConditionBadge({ condition }: { condition: Condition }) {
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      <span className="size-2 rounded-full" style={{ background: CONDITION_COLOR[condition] }} aria-hidden="true" />
      {CONDITION_LABEL[condition]}
    </Badge>
  )
}

export function ExitBadge({ status, live }: { status: ExitStatus | null; live?: boolean }) {
  if (live || status === null) {
    return (
      <StatusBadge tone="neutral" icon={<Loader2Icon className="animate-spin motion-reduce:animate-none" />}>
        running
      </StatusBadge>
    )
  }
  if (status === "submitted") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>submitted</StatusBadge>
  if (status === "budget") return <StatusBadge tone="warning" icon={<ClockIcon />}>budget</StatusBadge>
  if (status === "context_full") return <StatusBadge tone="serious" icon={<TriangleAlertIcon />}>context full</StatusBadge>
  return <StatusBadge tone="critical" icon={<OctagonXIcon />}>{status}</StatusBadge>
}

export function VerifyBadge({ verify }: { verify: VerifyState }) {
  if (verify === "ok") return <StatusBadge tone="good" icon={<ShieldCheckIcon />}>verified</StatusBadge>
  if (verify === "failed") return <StatusBadge tone="critical" icon={<OctagonXIcon />}>verify failed</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleHelpIcon />}>not verified</StatusBadge>
}

export function ConceptBadge({ status, pickedBy }: { status: ConceptStatus; pickedBy?: PickedBy | null }) {
  if (status === "picked") {
    return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>picked{pickedBy ? ` · ${pickedBy}` : ""}</StatusBadge>
  }
  if (status === "proposed") return <StatusBadge tone="warning" icon={<CircleDotIcon />}>proposed</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleDashedIcon />}>none</StatusBadge>
}

export function GoldBadge({ status }: { status: GoldStatus }) {
  if (status === "reviewed") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>reviewed</StatusBadge>
  if (status === "draft") return <StatusBadge tone="warning" icon={<PencilLineIcon />}>draft</StatusBadge>
  if (status === "building") return <StatusBadge tone="neutral" icon={<HammerIcon />}>building</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleSlashIcon />}>none</StatusBadge>
}

export function JobBadge({ state }: { state: JobState }) {
  if (state === "done") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>done</StatusBadge>
  if (state === "failed") return <StatusBadge tone="critical" icon={<OctagonXIcon />}>failed</StatusBadge>
  if (state === "running") {
    return <StatusBadge tone="neutral" icon={<Loader2Icon className="animate-spin motion-reduce:animate-none" />}>running</StatusBadge>
  }
  return <StatusBadge tone="neutral" icon={<ClockIcon />}>queued</StatusBadge>
}

/** A pulsing dot with a label for screen readers: the thing is live. */
export function LiveDot({ className }: { className?: string }) {
  return (
    <span className={cn("relative inline-flex size-2", className)} role="status" aria-label="live">
      <span className="absolute inline-flex size-full animate-ping rounded-full bg-status-good opacity-60 motion-reduce:animate-none" />
      <span className="relative inline-flex size-2 rounded-full bg-status-good" />
    </span>
  )
}
