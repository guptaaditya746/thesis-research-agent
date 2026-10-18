/**
 * Status badges. Colour never carries meaning alone: every status has an icon and a label.
 */
import { CheckCircle2Icon, ClockIcon, Loader2Icon, OctagonXIcon } from "lucide-react"
import type { ReactNode } from "react"

import type { JobState } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
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

const Spin = () => <Loader2Icon className="animate-spin motion-reduce:animate-none" />

export function JobBadge({ state }: { state: JobState }) {
  if (state === "done") return <StatusBadge tone="good" icon={<CheckCircle2Icon />}>done</StatusBadge>
  if (state === "failed") return <StatusBadge tone="critical" icon={<OctagonXIcon />}>failed</StatusBadge>
  if (state === "running") return <StatusBadge tone="neutral" icon={<Spin />}>running</StatusBadge>
  return <StatusBadge tone="neutral" icon={<ClockIcon />}>queued</StatusBadge>
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
