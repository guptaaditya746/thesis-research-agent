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
  FlaskConicalIcon,
  HammerIcon,
  Loader2Icon,
  OctagonXIcon,
  PencilLineIcon,
  ScissorsIcon,
  ShieldCheckIcon,
  TriangleAlertIcon,
} from "lucide-react"
import type { ReactNode } from "react"

import type { ConceptState, GoldState, JobState, VerifyState } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { CONDITION_COLOR, conditionLabel } from "@/lib/format"
import { cn } from "@/lib/utils"

export type Tone = "good" | "warning" | "serious" | "critical" | "neutral"

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

export function ConditionBadge({ condition }: { condition: string }) {
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      <span className="size-2 rounded-full" style={{ background: CONDITION_COLOR[condition] ?? "var(--muted-foreground)" }} aria-hidden="true" />
      {conditionLabel(condition)}
    </Badge>
  )
}

const Spin = () => <Loader2Icon className="animate-spin motion-reduce:animate-none" />

/** The run's exit status (agent/loop.py, the backend's running / incomplete / cut). */
export function ExitBadge({ status, live }: { status: string | null | undefined; live?: boolean }) {
  if (live || status === "running") return <StatusBadge tone="neutral" icon={<Spin />}>running</StatusBadge>
  if (status === "submitted") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>submitted</StatusBadge>
  if (status === "budget") return <StatusBadge tone="warning" icon={<ClockIcon />}>budget</StatusBadge>
  if (status === "context_full") return <StatusBadge tone="serious" icon={<TriangleAlertIcon />}>context full</StatusBadge>
  if (status === "cut") return <StatusBadge tone="serious" icon={<ScissorsIcon />} title="the batch job's time limit cut the run">cut</StatusBadge>
  if (status === "incomplete") return <StatusBadge tone="neutral" icon={<CircleDashedIcon />} title="the agent stopped writing without an outcome">incomplete</StatusBadge>
  return <StatusBadge tone="critical" icon={<OctagonXIcon />}>{status ?? "unknown"}</StatusBadge>
}

export function VerifyBadge({ verify }: { verify: VerifyState }) {
  if (verify === "ok") return <StatusBadge tone="good" icon={<ShieldCheckIcon />}>verified</StatusBadge>
  if (verify === "failed") return <StatusBadge tone="critical" icon={<OctagonXIcon />}>verify failed</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleHelpIcon />}>not verified</StatusBadge>
}

export function ConceptBadge({ status, pickedBy }: { status: ConceptState; pickedBy?: string | null }) {
  if (status === "picked") {
    return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>picked{pickedBy ? ` · ${pickedBy}` : ""}</StatusBadge>
  }
  if (status === "proposed") return <StatusBadge tone="warning" icon={<CircleDotIcon />}>proposed</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleDashedIcon />}>none</StatusBadge>
}

export function GoldBadge({ status }: { status: GoldState }) {
  if (status === "reviewed") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>reviewed</StatusBadge>
  if (status === "draft") return <StatusBadge tone="warning" icon={<PencilLineIcon />}>draft</StatusBadge>
  if (status === "building") return <StatusBadge tone="neutral" icon={<HammerIcon />}>building</StatusBadge>
  return <StatusBadge tone="neutral" icon={<CircleSlashIcon />}>none</StatusBadge>
}

export function JobBadge({ state }: { state: JobState }) {
  if (state === "done") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>done</StatusBadge>
  if (state === "failed") return <StatusBadge tone="critical" icon={<OctagonXIcon />}>failed</StatusBadge>
  if (state === "running") return <StatusBadge tone="neutral" icon={<Spin />}>running</StatusBadge>
  return <StatusBadge tone="neutral" icon={<ClockIcon />}>queued</StatusBadge>
}

/** A score against the draft key tests the pipeline; it is never a result. */
export function ProvisionalBadge() {
  return (
    <StatusBadge tone="warning" icon={<FlaskConicalIcon />} title="scored against the draft key (before review): tests the pipeline, never a result">
      provisional
    </StatusBadge>
  )
}

/** A pulsing dot with a label for screen readers: the thing is live. */
export function LiveDot({ className, label = "live" }: { className?: string; label?: string }) {
  return (
    <span className={cn("relative inline-flex size-2 shrink-0", className)} role="img" aria-label={label}>
      <span className="absolute inline-flex size-full animate-ping rounded-full bg-status-good opacity-60 motion-reduce:animate-none" />
      <span className="relative inline-flex size-2 rounded-full bg-status-good" />
    </span>
  )
}
