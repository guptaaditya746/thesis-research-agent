/** Smoke tests of the pages against the mock backend: each renders its data, its empty or its error state. */
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }

// The pages are lazy chunks (React Flow, recharts, ...). Load them once up front, so the
// per-test timeouts measure the UI and not module loading on a slow file system.
beforeAll(async () => {
  await Promise.all([
    import("@/pages/OverviewPage"), import("@/pages/QuestionPage"), import("@/pages/RunsPage"), import("@/pages/RunPage"),
    import("@/pages/ComparePage"), import("@/pages/ResultsPage"), import("@/pages/GoldPage"), import("@/pages/JobsPage"),
    import("@/pages/NotFoundPage"),
  ])
}, 180_000)

describe("pages", () => {
  it("overview lists the 12 questions with their pipeline state", async () => {
    renderRoutes(routes, "/")
    expect(await screen.findByRole("heading", { name: "Overview" }, T)).toBeInTheDocument()
    const table = await screen.findByRole("table", {}, T)
    expect(within(table).getAllByRole("row")).toHaveLength(13)
    expect(within(table).getByText("Which paper in this corpus is the most influential?")).toBeInTheDocument()
    expect(await screen.findByText("1 of 12", {}, T)).toBeInTheDocument() // gold keys reviewed
  })

  it("question page shows the briefs side by side and records a pick", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/questions/q07")
    const briefs = await screen.findByRole("list", { name: "Concept briefs" }, T)
    expect(briefs.querySelectorAll(":scope > [role=listitem]")).toHaveLength(3)
    expect(within(briefs).getAllByRole("button", { name: /^Pick brief \d$/ })).toHaveLength(3)
    expect(screen.getByText("No brief is picked yet. Compare the briefs and pick the one that makes the question answerable.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Pick brief 2" }))
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Reason"), "pairwise comparisons answer 'best'")
    await user.click(within(dialog).getByRole("button", { name: "Record the pick" }))
    expect(await screen.findByRole("button", { name: "Picked" }, T)).toBeDisabled()
    expect(screen.getByText(/picked by user/)).toBeInTheDocument()
  })

  it("question page offers to propose when there are no briefs", async () => {
    renderRoutes(routes, "/questions/q05")
    expect(await screen.findByText("No concept briefs yet", {}, T)).toBeInTheDocument()
  })

  it("runs page filters by condition through the URL", async () => {
    const { router } = renderRoutes(routes, "/runs?condition=claim_off")
    expect(await screen.findByText("q01-off-s1", {}, T)).toBeInTheDocument()
    expect(screen.queryByText("q01-on-s1")).not.toBeInTheDocument()
    expect(router.state.location.search).toBe("?condition=claim_off")
  })

  it("runs page has an empty state for filters that match nothing", async () => {
    renderRoutes(routes, "/runs?qid=q12")
    expect(await screen.findByText("No runs match these filters", {}, T)).toBeInTheDocument()
  })

  it("run page 404 says there is no such run", async () => {
    renderRoutes(routes, "/runs/nope")
    expect(await screen.findByText("No run nope", {}, T)).toBeInTheDocument()
  })

  it("results page shows the primary test and the per-question table", async () => {
    renderRoutes(routes, "/results")
    const primary = (await screen.findByText("Pre-registered primary outcome", {}, T)).closest<HTMLElement>("[data-slot=card]")!
    expect(within(primary).getByText("+19.0 pp")).toBeInTheDocument()
    expect(within(primary).getByText("significant at α = 0.05")).toBeInTheDocument()
    expect(within(primary).getByText("< 0.001")).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Support share by condition" })).toBeInTheDocument()
    expect(screen.getByText("Per question")).toBeInTheDocument()
  })

  it("results page explains a missing report", async () => {
    server.use(http.get("/api/results", () => HttpResponse.json({ detail: "no report" }, { status: 404 })))
    renderRoutes(routes, "/results")
    expect(await screen.findByText("No report yet", {}, T)).toBeInTheDocument()
  })

  it("gold page shows kappa and review progress", async () => {
    renderRoutes(routes, "/gold")
    expect(await screen.findByText("0.81", {}, T)).toBeInTheDocument()
    expect(screen.getByText("155 of 155 reviewed · 31 overlap")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Open Argilla/ })).toHaveAttribute("href", "http://127.0.0.1:6900")
  })

  it("compare page puts both conditions side by side with the differences", async () => {
    renderRoutes(routes, "/compare/q01")
    expect(await screen.findByText("claim on minus claim off", {}, T)).toBeInTheDocument()
    expect(screen.getByText("+10.0 pp")).toBeInTheDocument() // support share 0.6 vs 0.5
    expect(await screen.findByRole("list", { name: "Answer of q01-on-s1" }, T)).toBeInTheDocument()
    expect(screen.getByRole("list", { name: "Answer of q01-off-s1" })).toBeInTheDocument()
  })

  it("an API error shows the backend's reason and a retry", async () => {
    server.use(http.get("/api/gold", () => HttpResponse.json({ detail: "gold root missing" }, { status: 500 })))
    renderRoutes(routes, "/gold")
    const alert = await screen.findByRole("alert", {}, T)
    expect(alert).toHaveTextContent("gold root missing")
    expect(within(alert).getByRole("button", { name: /Try again/ })).toBeInTheDocument()
  })
})
