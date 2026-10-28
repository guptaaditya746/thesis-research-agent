/**
 * Where the person is in the flow, and how to go on: the stepper (Question, then the five steps of flow.ts), the
 * step's heading ("Step 3 of 6", what to do) and its footer (Back, Next; Next says why it is off). The design
 * rules: design-system/thesis-research-agent/pages/flow.md.
 */
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { STEPS, STEP_TEXT, TOTAL_STEPS, stepState, type Flow, type StepId } from "./flow"

function Dot({ done, active, n }: { done: boolean; active: boolean; n: number }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium tabular-nums transition-colors duration-(--motion-fast)",
        done && !active && "border-primary bg-primary text-primary-foreground",
        active && "border-2 border-primary bg-primary/10 text-primary",
        !done && !active && "border-input text-muted-foreground",
      )}
    >
      {done && !active ? <CheckIcon className="size-3.5" /> : n}
    </span>
  )
}

const ITEM = "flex min-h-11 min-w-11 items-center gap-2 rounded-md px-2 text-sm outline-none transition-colors duration-(--motion-fast) hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"

/**
 * The steps as links, numbered, with a check when chosen and the chosen value beside the label. The labels show
 * once the step bar is wide enough (a container query, so the sidebar's width counts); below that only the
 * numbers show, and the step heading says "Step n of 6". Each link's name (aria-label) is its label and value,
 * whatever is shown.
 */
export function Stepper({ flow, current }: { flow: Flow; current: StepId }) {
  const at = STEPS.findIndex((s) => s.id === current)
  return (
    <nav aria-label="Steps" className="@container rounded-xl border bg-card p-1">
      <ol className="flex items-center">
        <li className="flex flex-1 items-center">
          <Link to="/" aria-label="Question" title="Question" className={cn(ITEM, "text-muted-foreground")}>
            <Dot done active={false} n={1} />
            <span className="hidden whitespace-nowrap @2xl:inline">Question</span>
          </Link>
          <span aria-hidden="true" className="mx-1 h-px min-w-2 flex-1 bg-primary" />
        </li>
        {STEPS.map((s, n) => {
          const { done, value } = stepState(flow, s.id)
          const active = s.id === current
          const last = n === STEPS.length - 1
          return (
            <li key={s.id} className={cn("flex items-center", !last && "flex-1")}>
              <Link
                to={flow.href(s.id)}
                aria-current={active ? "step" : undefined}
                aria-label={value ? `${s.label}: ${value}` : s.label}
                title={value ? `${s.label}: ${value}` : s.label}
                className={cn(ITEM, active ? "bg-muted font-semibold text-foreground" : "text-muted-foreground hover:text-foreground", done && !active && "text-foreground")}
              >
                <Dot done={done} active={active} n={n + 2} />
                <span className="hidden whitespace-nowrap @2xl:inline">{s.label}</span>
                {/* the chosen value: always in the link's name and title, shown once there is room */}
                {value && <span className="hidden max-w-28 truncate font-mono text-xs text-muted-foreground @5xl:inline-block">{value}</span>}
              </Link>
              {!last && <span aria-hidden="true" className={cn("mx-1 h-px min-w-2 flex-1 transition-colors duration-(--motion-fast)", n < at || done ? "bg-primary" : "bg-border")} />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/** The step's heading: where you are (step n of 6), what the step is for. */
export function StepHeader({ step, children }: { step: StepId; children?: ReactNode }) {
  const n = STEPS.findIndex((s) => s.id === step) + 2
  const text = STEP_TEXT[step]
  return (
    <header className="space-y-1">
      <p className="text-xs font-semibold tracking-wide text-primary uppercase">Step {n} of {TOTAL_STEPS}</p>
      <h2 id="step-title" className="text-lg font-semibold tracking-tight">{text.title}</h2>
      <p className="max-w-prose text-sm text-muted-foreground">{text.hint}</p>
      {children}
    </header>
  )
}

/** Why Next is off on a step whose choice is not made yet. */
const NEEDS: Partial<Record<StepId, string>> = {
  protocol: "Choose a protocol to go on.",
  corpus: "Choose a corpus to go on.",
  run: "Choose an engine run to go on.",
}

/** Back to the step before (the questions, from the first step), Next to the step after once this one is chosen. */
export function StepFooter({ flow, step }: { flow: Flow; step: StepId }) {
  const at = STEPS.findIndex((s) => s.id === step)
  const prev = at > 0 ? STEPS[at - 1] : null
  const next = at < STEPS.length - 1 ? STEPS[at + 1] : null
  const { done } = stepState(flow, step)
  const ready = done || !NEEDS[step]
  return (
    <nav aria-label="Step navigation" className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <Button asChild variant="ghost">
        <Link to={prev ? flow.href(prev.id) : "/"}>
          <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" />
          {prev ? `Back: ${prev.label}` : "Back: Questions"}
        </Link>
      </Button>
      {next && (
        <div className="flex flex-wrap items-center justify-end gap-3">
          {!ready && <p id="step-next-why" className="text-sm text-muted-foreground">{NEEDS[step]}</p>}
          {ready ? (
            <Button asChild>
              <Link to={flow.href(next.id)}>
                Next: {next.label}
                <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
              </Link>
            </Button>
          ) : (
            <Button disabled aria-describedby="step-next-why">
              Next: {next.label}
              <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
            </Button>
          )}
        </div>
      )}
    </nav>
  )
}
