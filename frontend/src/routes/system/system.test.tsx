/** The one-page system page, boxes 1 to 3: each box opens only after the one above is done; the question box
 * drafts the protocol in one call; the run goes to the chosen folder. */
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { server } from "@/mocks/node"
import { renderWithProviders } from "@/test/render"

import type { PlanData, PlanDecision, PlanView } from "../plan/api"
import SystemPage from "./SystemPage"

const T = { timeout: 15_000 }
const WAIT = "Finish the box above first."
const decision = (id: string, over: Partial<PlanDecision> = {}): PlanDecision => ({
  id, type: "threshold", value: "0.01", reason: "noise", flagged: false, flag_reason: null, confirmed_by: null, confirmed_at: null, ...over,
})
const plan = (decisions: PlanDecision[], over: Partial<PlanData> = {}): PlanData => ({
  question: "Which conditions were studied?", field: "cs", main_rule: "any_line", clarifications: [], decisions,
  lines: [{ id: "l1", question: "Which conditions were studied?", query: "SELECT ?x WHERE {}", template: null, removable: true }],
  ...over,
})
const view = (decisions: PlanDecision[], over: Partial<PlanView> = {}, planOver: Partial<PlanData> = {}): PlanView => ({
  id: "p1", question: "Which conditions were studied?", clarifications: [], plan: plan(decisions, planOver), frozen: false, run: null,
  how: {}, problems: [], ready: decisions.every((d) => d.confirmed_by !== null), ...over,
})

async function chooseFolder(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("option", { name: "demo" }, T)
  await user.selectOptions(screen.getByRole("combobox", { name: "Domain" }), "demo")
  await user.selectOptions(screen.getByRole("combobox", { name: "Seed" }), "1")
}

describe("system page", () => {
  it("opens each box only after the one above is done", async () => {
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    expect(await screen.findByRole("combobox", { name: "Domain" }, T)).toBeInTheDocument()
    expect(screen.getAllByText(WAIT)).toHaveLength(2)
    expect(screen.queryByRole("textbox", { name: "Question" })).toBeNull()
    await chooseFolder(user)
    expect(screen.getByRole("textbox", { name: "Question" })).toBeInTheDocument()
    expect(screen.getAllByText(WAIT)).toHaveLength(1)
  })

  it("fills the question from the domain's file", async () => {
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    await chooseFolder(user)
    await user.selectOptions(screen.getByRole("combobox", { name: "Use a question from the domain's file" }), "d02")
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveValue("Which conditions were studied?")
    expect(screen.getByRole("textbox", { name: /Sub-questions/ })).toHaveValue("Which are the oldest?\nWhich have the most papers?")
    expect(screen.getByRole("combobox", { name: "How the answer is made" })).toHaveValue("inventory")
  })

  it("drafts the protocol with the sub-questions and the answer kind in one call", async () => {
    const bodies: unknown[] = []
    let answerCalls = 0
    server.use(
      http.post("/api/ev/plan", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json(view([decision("d1")])) }),
      http.post("/api/ev/plan/:id/answer", () => { answerCalls += 1; return HttpResponse.json(view([decision("d1")])) }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    await chooseFolder(user)
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Which conditions were studied?")
    await user.type(screen.getByRole("textbox", { name: /Sub-questions/ }), "Which are the oldest?")
    await user.selectOptions(screen.getByRole("combobox", { name: "How the answer is made" }), "inventory")
    await user.selectOptions(screen.getByRole("combobox", { name: "Target" }), "metric")
    await user.click(screen.getByRole("button", { name: "Draft the protocol" }))
    await waitFor(() => expect(bodies).toHaveLength(1), T)
    expect(bodies[0]).toEqual({ question: "Which conditions were studied?", sub_questions: ["Which are the oldest?"], answer_by: "inventory", target: "metric" })
    expect(answerCalls).toBe(0)
  })

  it("keeps the answer kind when the planner asks a clarifying question", async () => {
    const clarified: unknown[] = []
    server.use(
      http.post("/api/ev/plan", () => HttpResponse.json(view([], { plan: null, clarifications: [{ question: "Which one?", options: ["this", "that"] }] }))),
      http.post("/api/ev/plan/:id/clarify", async ({ request }) => {
        clarified.push(await request.json())
        return HttpResponse.json(view([decision("d1")], {}, { answer_by: "inventory", target: "metric" }))
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    await chooseFolder(user)
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Which conditions were studied?")
    await user.selectOptions(screen.getByRole("combobox", { name: "How the answer is made" }), "inventory")
    await user.click(screen.getByRole("button", { name: "Draft the protocol" }))
    await user.click(await screen.findByRole("button", { name: "this" }, T))
    await user.click(screen.getByRole("button", { name: "Make the plan" }))
    await waitFor(() => expect(clarified).toHaveLength(1), T)
    expect(await screen.findByText("Answer kind: inventory", {}, T)).toBeInTheDocument()
  })

  it("opens a question's batch plan", async () => {
    const opened: string[] = []
    server.use(
      http.get("/api/ev/system/domains", () => HttpResponse.json([{
        domain: "demo", seeds: [1], error: null,
        questions: [{ id: "d01", question: "Does it help?", sub_questions: [], kind: "effect", target: null, plan: "draft" }],
      }])),
      http.post("/api/ev/plan/batch/:domain/:qid", ({ params }) => { opened.push(`${String(params.domain)}/${String(params.qid)}`); return HttpResponse.json(view([decision("d1")], { batch: "demo/d01" })) }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    await chooseFolder(user)
    await user.selectOptions(screen.getByRole("combobox", { name: "Use a question from the domain's file" }), "d01")
    expect(screen.getByRole("link", { name: "edit on the plan page" })).toHaveAttribute("href", "/plan?batch=demo/d01")
    await user.click(screen.getByRole("button", { name: "Open its batch plan" }))
    await waitFor(() => expect(opened).toEqual(["demo/d01"]), T)
  })

  it("runs on the chosen folder only when every decision is confirmed", async () => {
    const runs: unknown[] = []
    let decisions = [decision("d1"), decision("d2")]
    server.use(
      http.post("/api/ev/plan", () => HttpResponse.json(view(decisions))),
      http.post("/api/ev/plan/p1/confirm-all", () => {
        decisions = decisions.map((d) => ({ ...d, confirmed_by: "ada" }))
        return HttpResponse.json(view(decisions))
      }),
      http.post("/api/ev/plan/p1/run", async ({ request }) => { runs.push(await request.json()); return HttpResponse.json({ run: "r1" }) }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SystemPage />)
    await chooseFolder(user)
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Which conditions were studied?")
    await user.click(screen.getByRole("button", { name: "Draft the protocol" }))
    const run = await screen.findByRole("button", { name: "Run on demo s1" }, T)
    expect(run).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Confirm all" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Run on demo s1" })).toBeEnabled(), T)
    await user.click(screen.getByRole("button", { name: "Run on demo s1" }))
    await waitFor(() => expect(runs).toEqual([{ domain: "demo", seed: 1 }]), T)
  })
})
