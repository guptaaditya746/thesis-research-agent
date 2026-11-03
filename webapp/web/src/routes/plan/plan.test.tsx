/** The planner page: Run stays disabled until every decision is confirmed, a flagged decision is highlighted
 * with its reason, a failed line says "failed: <reason>", the answer says "missing: <line>". */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { server } from "@/mocks/node"
import { renderWithProviders } from "@/test/render"

import type { PlanData, PlanDecision, PlanResult, PlanView } from "./api"
import { DecisionsPanel } from "./DecisionsPanel"
import { LineCard } from "./LineCard"
import PlanPage from "./PlanPage"

const T = { timeout: 15_000 }
const decision = (id: string, over: Partial<PlanDecision> = {}): PlanDecision => ({
  id, type: "threshold", value: "0.01", reason: "noise", flagged: false, flag_reason: null, confirmed_by: null, confirmed_at: null, ...over,
})
const plan = (decisions: PlanDecision[]): PlanData => ({
  question: "Does it help?", field: "cs", main_rule: "majority of lines", clarifications: [], decisions,
  lines: [
    { id: "l1", question: "Does it help?", query: "SELECT ?x WHERE {}", template: null, removable: true },
    { id: "oversell", question: "Oversold?", query: "SELECT ?y WHERE {}", template: "oversell", removable: false },
  ],
})
const view = (decisions: PlanDecision[], extra: Partial<PlanView> = {}): PlanView => ({
  id: "p1", question: "Does it help?", clarifications: [], plan: plan(decisions), frozen: false, run: null,
  how: { l1: ["It looks at every claim.", "It keeps the big numbers."], oversell: ["It finds firm claims the numbers do not back."] },
  problems: [], ready: decisions.every((d) => d.confirmed_by !== null), ...extra,
})

describe("decisions panel", () => {
  it("highlights a flagged decision with its reason and marks LLM choices", () => {
    renderWithProviders(<DecisionsPanel decisions={[decision("d1", { flagged: true, flag_reason: "maybe too small" }), decision("d2", { confirmed_by: "ada" })]}
      onConfirm={() => {}} onChange={() => {}} onConfirmAll={() => {}} />)
    const flagged = document.querySelector("[data-decision=d1]") as HTMLElement
    expect(flagged).toHaveAttribute("data-flagged", "true")
    expect(within(flagged).getByText(/maybe too small/)).toBeInTheDocument()
    expect(within(flagged).getByText("made by LLM")).toBeInTheDocument()
    expect(screen.getByText("confirmed by ada")).toBeInTheDocument()
  })
})

describe("line card", () => {
  it("has no × on the oversell line, a closed how?, and shows failed and empty results", () => {
    const base = plan([]).lines
    const { rerender } = renderWithProviders(<LineCard line={base[1]} onRemove={() => {}} />)
    expect(screen.queryByRole("button", { name: /Remove line/ })).toBeNull()
    rerender(<LineCard line={base[0]} how={["It looks at every claim."]} onRemove={() => {}} result={{ id: "l1", question: "Does it help?", status: "failed", rows: [], text: "failed: bad query" }} />)
    expect(screen.getByRole("button", { name: /Remove line/ })).toBeInTheDocument()
    expect(screen.getByText("failed: bad query")).toBeInTheDocument()
    expect(document.querySelector("details")).not.toHaveAttribute("open")
    expect(screen.getByText("It looks at every claim.")).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/SELECT/)
    rerender(<LineCard line={base[0]} result={{ id: "l1", question: "x", status: "done", rows: [], text: "0 found" }} />)
    expect(screen.getByText("No evidence found")).toBeInTheDocument()
  })
})

describe("decisions panel changes", () => {
  it("sends a number as a number and offers only the fixed rules for the main rule", async () => {
    const changes: [string, unknown][] = []
    const user = userEvent.setup()
    renderWithProviders(<DecisionsPanel decisions={[decision("d1"), decision("main_rule", { type: "counts_as", value: "any_line" })]}
      onConfirm={() => {}} onChange={(id, v) => changes.push([id, v])} onConfirmAll={() => {}} />)
    const [first, second] = screen.getAllByRole("button", { name: "Change" })
    await user.click(first)
    const box = screen.getByRole("textbox", { name: /New value/ })
    await user.clear(box)
    await user.type(box, "0.05")
    await user.click(screen.getByRole("button", { name: "Save" }))
    await user.click(second)
    await user.selectOptions(screen.getByRole("combobox", { name: "Main answer rule" }), "majority")
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(changes).toEqual([["d1", 0.05], ["main_rule", "majority"]])
  })
})

describe("plan page", () => {
  it("shows the problems and keeps Run disabled even when every decision is confirmed", async () => {
    server.use(http.post("/api/ev/plan", () => HttpResponse.json(view([decision("d1", { confirmed_by: "ada" })], { problems: ["the plan has no evidence line"], ready: false }))))
    const user = userEvent.setup()
    renderWithProviders(<PlanPage />)
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Does it help?")
    await user.click(screen.getByRole("button", { name: "Plan" }))
    expect(await screen.findByText("the plan has no evidence line", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled()
  })

  it("keeps Run disabled until every decision is confirmed, then runs and shows failed and missing", async () => {
    let decisions = [decision("d1", { flagged: true, flag_reason: "maybe too small" }), decision("d2")]
    let run: string | null = null
    const result: PlanResult = {
      status: "done",
      lines: [
        { id: "l1", question: "Does it help?", status: "failed", rows: [], text: "failed: bad query" },
        { id: "oversell", question: "Oversold?", status: "done", rows: [], text: "0 found" },
      ],
      answer: { text: "No evidence found", missing: ["missing: Does it help?"] },
      reruns: [{ setting: "threshold 0.05", flips: true }, { setting: "include all", flips: false }],
    }
    server.use(
      http.post("/api/ev/plan", () => HttpResponse.json(view(decisions))),
      http.post("/api/ev/plan/p1/confirm-all", () => {
        decisions = decisions.map((d) => ({ ...d, confirmed_by: "ada" }))
        return HttpResponse.json(view(decisions))
      }),
      http.post("/api/ev/plan/p1/run", () => { run = "r1"; return HttpResponse.json({ run: "r1" }) }),
      http.get("/api/ev/plan/p1/result", () => HttpResponse.json(result)),
    )
    const user = userEvent.setup()
    renderWithProviders(<PlanPage />)
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Does it help?")
    await user.click(screen.getByRole("button", { name: "Plan" }))
    const runButton = await screen.findByRole("button", { name: "Run" }, T)
    expect(runButton).toBeDisabled()
    expect(screen.queryByRole("button", { name: /Remove line: Oversold/ })).toBeNull()
    await user.click(screen.getByRole("button", { name: "Confirm all" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeEnabled(), T)
    await user.click(screen.getByRole("button", { name: "Run" }))
    expect(await screen.findByText("failed: bad query", {}, T)).toBeInTheDocument()
    expect(screen.getByText("missing: Does it help?")).toBeInTheDocument()
    expect(screen.getByText("threshold 0.05")).toBeInTheDocument()
    expect(screen.queryByText("include all")).toBeNull() // only the settings that flip the answer
    expect(run).toBe("r1")
  })
})
