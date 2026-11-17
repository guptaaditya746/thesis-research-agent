/** The review page: approve worlds, edit and check answer sheets, hand-mark the judge-test answers. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

import type { JudgeItem, SheetView, WorldRow } from "./api"
import ReviewPage from "./ReviewPage"

const T = { timeout: 15_000 }
const routes = [{ path: "/review", element: <ReviewPage /> }, { path: "/review/:tab", element: <ReviewPage /> }]
const overview = http.get("/api/ev/review", () => HttpResponse.json({ domains: [{ domain: "demo", questions: 3, seeds: [1], worlds: [1] }] }))
const queue = http.get("/api/ev/review/demo/sheets", () =>
  HttpResponse.json([{ seed: 1, question_id: "d01", status: "drafted", stale: null, must_check: "full" }]))

const sheetView = (over: Partial<SheetView> = {}): SheetView => ({
  question: "Does Targeted therapy change the Response rate?",
  sub_questions: ["Is it faster?"],
  scope: { arms: ["Targeted therapy", "Standard care"], measures: [], conditions: [], settings: [] },
  facts: [{ id: "pair:a:m1", text: "Response rate: 0.4 vs 0.3" }],
  sheet: { status: "drafted", points: [{ id: "p1", text: "Original.", facts: ["pair:a:m1"] }], warnings: [], checked_by: null },
  stale: null,
  ...over,
})

async function openSheet(view: SheetView, bodies: unknown[]) {
  server.use(
    overview, queue,
    http.get("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json(view)),
    http.put("/api/ev/review/demo/sheets/1/d01", async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json({ status: "checked" })
    }),
  )
  const user = userEvent.setup()
  renderRoutes(routes, "/review/sheets")
  await user.click(await screen.findByRole("button", { name: /d01/ }, T))
  return user
}

describe("review page: answer sheets", () => {
  it("saves edited points as checked", async () => {
    const bodies: unknown[] = []
    const user = await openSheet(sheetView(), bodies)
    expect(await screen.findByText("for planning only; not scored", { exact: false }, T)).toBeInTheDocument()
    expect(screen.getByText("about: Targeted therapy, Standard care; measures: all")).toBeInTheDocument()
    const box = await screen.findByRole("textbox", { name: "Point 1" }, T)
    await user.clear(box)
    await user.type(box, "Edited.")
    await user.click(screen.getByRole("button", { name: "Save and mark checked" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "Edited.", facts: ["pair:a:m1"] }] }]), T)
  })

  it("saves a stale sheet as a new sheet", async () => {
    const bodies: unknown[] = []
    const user = await openSheet(sheetView({ stale: "the question changed after drafting" }), bodies)
    expect(await screen.findByText(/the question changed after drafting/, {}, T)).toBeInTheDocument()
    const box = screen.getByRole("textbox", { name: "Point 1" })
    await user.clear(box)
    await user.type(box, "Edited.")
    await user.click(screen.getByRole("button", { name: "Save as a new sheet" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "Edited.", facts: ["pair:a:m1"] }] }]), T)
  })

  it("writes a missing sheet", async () => {
    const bodies: unknown[] = []
    const user = await openSheet(sheetView({ sheet: null }), bodies)
    await user.click(await screen.findByRole("button", { name: "Add point" }, T))
    await user.type(screen.getByRole("textbox", { name: "Point 1" }), "By hand.")
    await user.click(screen.getByRole("button", { name: "Write and mark checked" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "By hand.", facts: [] }] }]), T)
  })

  it("shows a refusal near Save and keeps the text", async () => {
    server.use(
      overview, queue,
      http.get("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json(sheetView())),
      http.put("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json({ detail: "unknown fact pair:zz:m9" }, { status: 400 })),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review/sheets")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const box = await screen.findByRole("textbox", { name: "Point 1" }, T)
    await user.clear(box)
    await user.type(box, "Mine.")
    await user.click(screen.getByRole("button", { name: "Save and mark checked" }))
    expect(await screen.findByText(/unknown fact pair:zz:m9/, {}, T)).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Point 1" })).toHaveValue("Mine.")
  })
})

describe("review page: judge test", () => {
  const item: JudgeItem = {
    n: 0, domain: "demo", seed: 1, question_id: "d01", question: "Does it help?", answer: "It helps.",
    points: [{ id: "p1", text: "It helps." }], facts: [{ n: 1, paper: "S001", quote: "first quote" }], facts_cut: false, marked: null,
  }
  it("hand-marks a judge-test answer without showing the judge", async () => {
    const bodies: unknown[] = []
    server.use(
      overview,
      http.get("/api/ev/review/judge-test", () => HttpResponse.json([
        { n: 0, domain: "demo", seed: 1, question_id: "d01", done: false },
        { n: 1, problem: "a row of sample.json is not valid", done: false },
      ])),
      http.get("/api/ev/review/judge-test/0", () => HttpResponse.json(item)),
      http.put("/api/ev/review/judge-test/0", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({}) }),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review/judge-test")
    expect(await screen.findByText(/a row of sample.json is not valid/, {}, T)).toBeInTheDocument()
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const panel = await screen.findByRole("region", { name: "Judge-test item" }, T)
    expect(within(panel).getByText(/first quote/)).toBeInTheDocument()
    expect(within(panel).queryByText(/judge|score/i)).toBeNull()
    await user.click(within(panel).getByRole("radio", { name: "Met" }))
    await user.click(within(panel).getByRole("button", { name: "Save" }))
    await waitFor(() => expect(bodies).toEqual([{ points: { p1: true }, faithful: null }]), T)
  })
})

describe("review page: worlds", () => {
  it("approves a world", async () => {
    const bodies: unknown[] = []
    const row: WorldRow = { seed: 1, approved: false, text: "World of demo, seed 1", path: "worlds/demo/s1.json" }
    server.use(
      overview,
      http.get("/api/ev/review/demo/worlds", () => HttpResponse.json([row])),
      http.put("/api/ev/review/demo/worlds/1", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({ ...row, approved: true }) }),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review")
    expect(await screen.findByText("Not approved", {}, T)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Approve" }))
    await user.click(await screen.findByRole("button", { name: "Yes, approve" }))
    await waitFor(() => expect(bodies).toEqual([{ approved: true }]), T)
  })

  it("lists a broken spec with its error instead of crashing", async () => {
    server.use(http.get("/api/ev/review", () => HttpResponse.json({ domains: [{ domain: "other", questions: null, seeds: [], worlds: [], error: "other.yaml: bad" }] })))
    renderRoutes(routes, "/review")
    expect(await screen.findByText(/other.yaml: bad/, {}, T)).toBeInTheDocument()
  })
})
