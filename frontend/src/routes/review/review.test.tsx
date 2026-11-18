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
  shown: "s1",
  stale: null,
  ...over,
})

async function openSheet(view: SheetView, bodies: unknown[]) {
  server.use(
    overview, queue,
    http.get("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json(view)),
    http.put("/api/ev/review/demo/sheets/1/d01", async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json({ status: "checked", shown: "s2" })
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
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "Edited.", facts: ["pair:a:m1"] }], shown: "s1" }]), T)
  })

  it("keeps the typed text and turns Save off when the sheet changed on disk, until the new sheet is loaded", async () => {
    // review round 1, web-I3: a redraft on disk changed the header and facts but not the points, and Save wrote
    // the old points over the new draft
    const bodies: unknown[] = []
    let current = sheetView()
    server.use(
      overview, queue,
      http.get("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json(current)),
      http.put("/api/ev/review/demo/sheets/1/d01", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({ status: "checked", shown: "s9" }) }),
    )
    const user = userEvent.setup()
    const { client } = renderRoutes(routes, "/review/sheets")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const box = await screen.findByRole("textbox", { name: "Point 1" }, T)
    await user.clear(box)
    await user.type(box, "Mine.")
    current = sheetView({ shown: "s2", sheet: { status: "drafted", points: [{ id: "p1", text: "Redrafted.", facts: [] }], warnings: [], checked_by: null } })
    await client.invalidateQueries({ queryKey: ["review", "demo", "sheet", 1, "d01"] })
    expect(await screen.findByText(/This sheet changed on disk after you opened it/, {}, T)).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Point 1" })).toHaveValue("Mine.")
    expect(screen.getByRole("button", { name: "Save and mark checked" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Load the sheet as it is now" }))
    expect(screen.getByRole("textbox", { name: "Point 1" })).toHaveValue("Redrafted.")
    await user.click(screen.getByRole("button", { name: "Save and mark checked" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "Redrafted.", facts: [] }], shown: "s2" }]), T)
  })

  it("does not take its own save for a change on disk", async () => {
    const bodies: unknown[] = []
    let current = sheetView()
    server.use(
      overview, queue,
      http.get("/api/ev/review/demo/sheets/1/d01", () => HttpResponse.json(current)),
      http.put("/api/ev/review/demo/sheets/1/d01", async ({ request }) => {
        bodies.push(await request.json())
        current = sheetView({ shown: "s2", sheet: { status: "checked", points: [{ id: "p1", text: "Edited.", facts: ["pair:a:m1"] }], warnings: [], checked_by: "ada" } })
        return HttpResponse.json({ status: "checked", shown: "s2" })
      }),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review/sheets")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const box = await screen.findByRole("textbox", { name: "Point 1" }, T)
    await user.clear(box)
    await user.type(box, "Edited.")
    await user.click(screen.getByRole("button", { name: "Save and mark checked" }))
    expect(await screen.findByText("Saved.", {}, T)).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 300))   // the queue and the sheet are read again after a save
    expect(screen.queryByText(/This sheet changed on disk/)).toBeNull()
    await user.click(screen.getByRole("button", { name: "Save and mark checked" }))
    await waitFor(() => expect(bodies[1]).toEqual({ points: [{ text: "Edited.", facts: ["pair:a:m1"] }], shown: "s2" }), T)
  })

  it("saves a stale sheet as a new sheet", async () => {
    const bodies: unknown[] = []
    const user = await openSheet(sheetView({ stale: "the question changed after drafting" }), bodies)
    expect(await screen.findByText(/the question changed after drafting/, {}, T)).toBeInTheDocument()
    const box = screen.getByRole("textbox", { name: "Point 1" })
    await user.clear(box)
    await user.type(box, "Edited.")
    await user.click(screen.getByRole("button", { name: "Save as a new sheet" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "Edited.", facts: ["pair:a:m1"] }], shown: "s1" }]), T)
  })

  it("writes a missing sheet", async () => {
    const bodies: unknown[] = []
    const user = await openSheet(sheetView({ sheet: null, shown: null }), bodies)
    await user.click(await screen.findByRole("button", { name: "Add point" }, T))
    await user.type(screen.getByRole("textbox", { name: "Point 1" }), "By hand.")
    await user.click(screen.getByRole("button", { name: "Write and mark checked" }))
    await waitFor(() => expect(bodies).toEqual([{ points: [{ text: "By hand.", facts: [] }], shown: null }]), T)
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
    points: [{ id: "p1", text: "It helps." }], facts: [{ n: 1, paper: "S001", quote: "first quote" }], facts_cut: false, marked: null, note: null,
    shown: "i1",
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
    await waitFor(() => expect(bodies).toEqual([{ points: { p1: true }, faithful: null, shown: "i1" }]), T)
  })

  it("clears the ticks when the item under them changes, and a save names what is shown", async () => {
    // review round 1, web-I3: a judge run while the item was open swapped the answer and the points; the old
    // tick stayed on, Save was enabled and the old tick was stored for the new answer
    const bodies: unknown[] = []
    let current: JudgeItem = { ...item, answer: "OLD ANSWER: it helps.", points: [{ id: "p1", text: "Old point." }] }
    server.use(
      overview,
      http.get("/api/ev/review/judge-test", () => HttpResponse.json([{ n: 0, domain: "demo", seed: 1, question_id: "d01", done: false }])),
      http.get("/api/ev/review/judge-test/0", () => HttpResponse.json(current)),
      http.put("/api/ev/review/judge-test/0", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({}) }),
    )
    const user = userEvent.setup()
    const { client } = renderRoutes(routes, "/review/judge-test")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const panel = await screen.findByRole("region", { name: "Judge-test item" }, T)
    await user.click(within(panel).getByRole("radio", { name: "Met" }))
    current = { ...item, answer: "NEW ANSWER: it hurts.", points: [{ id: "p1", text: "New point." }], shown: "i2" }
    await client.invalidateQueries({ queryKey: ["review", "judge-test", 0] })
    await screen.findByText(/NEW ANSWER/, {}, T)
    const now = screen.getByRole("region", { name: "Judge-test item" })
    expect(within(now).getByText("New point.")).toBeInTheDocument()
    expect(within(now).getByRole("radio", { name: "Met" })).not.toBeChecked()
    expect(within(now).getByRole("button", { name: "Save" })).toBeDisabled()
    await user.click(within(now).getByRole("radio", { name: "Not met" }))
    await user.click(within(now).getByRole("button", { name: "Save" }))
    await waitFor(() => expect(bodies).toEqual([{ points: { p1: false }, faithful: null, shown: "i2" }]), T)
  })

  it("shows a refused save and loads the item again", async () => {
    let gets = 0
    server.use(
      overview,
      http.get("/api/ev/review/judge-test", () => HttpResponse.json([{ n: 0, domain: "demo", seed: 1, question_id: "d01", done: false }])),
      http.get("/api/ev/review/judge-test/0", () => { gets += 1; return HttpResponse.json(gets === 1 ? item : { ...item, answer: "NEW ANSWER.", shown: "i2" }) }),
      http.put("/api/ev/review/judge-test/0", () => HttpResponse.json({ detail: "judge-test item 0: the item changed since the page showed it" }, { status: 409 })),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review/judge-test")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    const panel = await screen.findByRole("region", { name: "Judge-test item" }, T)
    await user.click(within(panel).getByRole("radio", { name: "Met" }))
    await user.click(within(panel).getByRole("button", { name: "Save" }))
    expect(await screen.findByText(/the item changed since the page showed it/, {}, T)).toBeInTheDocument()
    expect(await screen.findByText("NEW ANSWER.", {}, T)).toBeInTheDocument()
    expect(screen.getByText(/the item changed since the page showed it/)).toBeInTheDocument()   // still said
    expect(screen.getByRole("radio", { name: "Met" })).not.toBeChecked()
  })

  async function openItem(over: Partial<JudgeItem>, bodies: unknown[]) {
    server.use(
      overview,
      http.get("/api/ev/review/judge-test", () => HttpResponse.json([
        { n: 0, domain: "demo", seed: 1, question_id: "d01", done: false },
        { n: 1, problem: "a row of sample.json is not valid", done: false },
      ])),
      http.get("/api/ev/review/judge-test/0", () => HttpResponse.json({ ...item, ...over })),
      http.put("/api/ev/review/judge-test/0", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({}) }),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review/judge-test")
    await user.click(await screen.findByRole("button", { name: /d01/ }, T))
    return { user, panel: await screen.findByRole("region", { name: "Judge-test item" }, T) }
  }

  it("cannot open a broken row", async () => {
    await openItem({}, [])
    expect(screen.getByRole("button", { name: "Row 2" })).toBeDisabled()
  })

  it("saves Not met with faithful yes, then no", async () => {
    const bodies: unknown[] = []
    const { user, panel } = await openItem({}, bodies)
    await user.click(within(panel).getByRole("radio", { name: "Not met" }))
    await user.click(within(panel).getByRole("radio", { name: "yes" }))
    await user.click(within(panel).getByRole("button", { name: "Save" }))
    await waitFor(() => expect(bodies).toEqual([{ points: { p1: false }, faithful: true, shown: "i1" }]), T)
    await user.click(within(panel).getByRole("radio", { name: "no" }))
    await user.click(within(panel).getByRole("button", { name: "Save" }))
    await waitFor(() => expect(bodies[1]).toEqual({ points: { p1: false }, faithful: false, shown: "i1" }), T)
  })

  it("says when some facts were cut", async () => {
    const { panel } = await openItem({ facts_cut: true }, [])
    expect(within(panel).getByText("Some were cut for length.")).toBeInTheDocument()
  })

  it("asks to mark again when the answer or its sheet changed", async () => {
    const { panel } = await openItem({ marked: null, note: "the answer or its sheet changed since you marked it" }, [])
    expect(within(panel).getByText(/the answer or its sheet changed since you marked it/)).toBeInTheDocument()
    expect(within(panel).getByRole("radio", { name: "Met" })).not.toBeChecked()
    expect(within(panel).getByRole("button", { name: "Save" })).toBeDisabled()
  })
})

describe("review page: sheet queue", () => {
  it("puts the must-check rows first and can show the API order", async () => {
    server.use(overview, http.get("/api/ev/review/demo/sheets", () => HttpResponse.json([
      { seed: 2, question_id: "d02", status: "drafted", stale: null, must_check: "sample" },
      { seed: 3, question_id: "d03", status: "drafted", stale: null, must_check: null },
      { seed: 1, question_id: "d01", status: "drafted", stale: null, must_check: "full" },
    ])))
    const user = userEvent.setup()
    renderRoutes(routes, "/review/sheets")
    await screen.findByRole("button", { name: "d01" }, T)
    const order = () => screen.getAllByRole("button", { name: /^d0\d$/ }).map((b) => b.textContent)
    expect(order()).toEqual(["d01", "d02", "d03"])
    await user.click(screen.getByRole("button", { name: "Must check" }))
    expect(order()).toEqual(["d02", "d03", "d01"])
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

  it("withdraws an approval, and Cancel sends nothing", async () => {
    const bodies: unknown[] = []
    const row: WorldRow = { seed: 1, approved: true, text: "World of demo, seed 1", path: "worlds/demo/s1.json" }
    server.use(
      overview,
      http.get("/api/ev/review/demo/worlds", () => HttpResponse.json([row])),
      http.put("/api/ev/review/demo/worlds/1", async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({ ...row, approved: false }) }),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review")
    await user.click(await screen.findByRole("button", { name: "Withdraw approval" }, T))
    await user.click(await screen.findByRole("button", { name: "Cancel" }))
    expect(bodies).toEqual([])
    await user.click(screen.getByRole("button", { name: "Withdraw approval" }))
    await user.click(await screen.findByRole("button", { name: "Yes, withdraw" }))
    await waitFor(() => expect(bodies).toEqual([{ approved: false }]), T)
  })

  it("shows a refused approve", async () => {
    const row: WorldRow = { seed: 1, approved: false, text: "World of demo, seed 1", path: "worlds/demo/s1.json" }
    server.use(
      overview,
      http.get("/api/ev/review/demo/worlds", () => HttpResponse.json([row])),
      http.put("/api/ev/review/demo/worlds/1", () => HttpResponse.json({ detail: "the world file does not load" }, { status: 422 })),
    )
    const user = userEvent.setup()
    renderRoutes(routes, "/review")
    await user.click(await screen.findByRole("button", { name: "Approve" }, T))
    await user.click(await screen.findByRole("button", { name: "Yes, approve" }))
    expect(await screen.findByText(/the world file does not load/, {}, T)).toBeInTheDocument()
  })

  it("lists a broken spec with its error instead of crashing", async () => {
    server.use(http.get("/api/ev/review", () => HttpResponse.json({ domains: [{ domain: "other", questions: null, seeds: [], worlds: [], error: "other.yaml: bad" }] })))
    renderRoutes(routes, "/review")
    expect(await screen.findByText(/other.yaml: bad/, {}, T)).toBeInTheDocument()
  })
})
