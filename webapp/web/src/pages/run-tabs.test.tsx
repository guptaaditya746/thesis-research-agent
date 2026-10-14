/** The run page's tabs against the mock backend, and the jobs page. */
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { PASSAGES, quoteOf } from "@/mocks/fixtures"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }

beforeAll(async () => {
  await Promise.all([import("@/pages/RunPage"), import("@/pages/JobsPage")])
}, 180_000)

describe("run page tabs", () => {
  it("header shows the run's stats against its budget", async () => {
    renderRoutes(routes, "/runs/q01-on-s1")
    expect(await screen.findByRole("heading", { name: "q01-on-s1" }, T)).toBeInTheDocument()
    expect(screen.getByText("71.4K")).toBeInTheDocument()
    expect(screen.getByText("/ 2M")).toBeInTheDocument()
    expect(screen.getByText("/ 60")).toBeInTheDocument()
    expect(screen.getByText("verified")).toBeInTheDocument()
    expect(screen.getByText("submitted")).toBeInTheDocument()
  })

  it("graph: edges open the walk of the fact that cites them, or of the bare claim", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/runs/q01-on-s1?tab=graph")
    expect(await screen.findByRole("region", { name: "Knowledge graph" }, T)).toBeInTheDocument()
    await user.click(screen.getByText("Edges as a list (7)"))
    await user.click(screen.getByRole("button", { name: "p1 —evaluatesOn→ Spider" }))
    let sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByRole("heading", { name: "Claim walk · f1" })).toBeInTheDocument()
    await user.keyboard("{Escape}")
    await user.click(screen.getByRole("button", { name: "p4 —title→ “MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval”" }))
    sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByTestId("quote")).toHaveTextContent(quoteOf(PASSAGES.megapairs))
    expect(within(sheet).getByText(/no answer fact cites it/)).toBeInTheDocument()
  })

  it("graph: an empty graph says why", async () => {
    renderRoutes(routes, "/runs/q01-on-s2?tab=graph")
    expect(await screen.findByText("The graph is empty", {}, T)).toBeInTheDocument()
  })

  it("timeline: steps in order with sub-agent, claims, rejected reason and the budget", async () => {
    renderRoutes(routes, "/runs/q01-on-s1?tab=timeline")
    const steps = await screen.findByRole("list", { name: "Steps" }, T)
    expect(within(steps).getByText("Step 1")).toBeInTheDocument()
    expect(within(steps).getByText("Step 8")).toBeInTheDocument()
    expect(within(steps).getByText("sub-01")).toBeInTheDocument()
    expect(within(steps).getByText("not_found")).toBeInTheDocument()
    expect(screen.getByText("Research steps")).toBeInTheDocument()
    expect(screen.getByText("of 60")).toBeInTheDocument()
  })

  it("timeline: a coverage notice explains itself", async () => {
    renderRoutes(routes, "/runs/q01-on-s2?tab=timeline")
    expect(await screen.findByText("coverage: unparsed", {}, T)).toBeInTheDocument()
    expect(screen.getByText(/The reply had no bash block/)).toBeInTheDocument()
  })

  it("claims: filter to the rejected ones and walk an accepted one", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/runs/q01-on-s1?tab=claims")
    const search = await screen.findByRole("searchbox", { name: "Search" }, T)
    const table = screen.getByRole("table")
    expect(within(table).getAllByRole("row")).toHaveLength(9) // header + 8 claims
    await user.type(search, "hellaswag")
    expect(within(table).getAllByRole("row")).toHaveLength(2)
    expect(within(table).getByText("not_found")).toBeInTheDocument()
    await user.clear(search)
    await user.click(within(table).getAllByRole("button", { name: "Walk" })[0])
    expect(await screen.findByRole("dialog")).toBeInTheDocument()
  })

  it("provenance: runs a query and a SPARQL query", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/runs/q01-on-s1?tab=provenance")
    await user.click(await screen.findByRole("button", { name: "Run query 5" }, T))
    const result = await screen.findByRole("table", { name: "Query 5 results" })
    expect(within(result).getByText("HellaSwag")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Run query 3" }))
    expect(await screen.findByText("query 3 needs a step, an agent, or both")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Run" }))
    expect(await screen.findByText("7 rows")).toBeInTheDocument()
  })

  it("score: the support breakdown and the facts against the key", async () => {
    renderRoutes(routes, "/runs/q01-on-s1?tab=score")
    expect(await screen.findByText("60.0%", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "3 supported, 1 partial, 0 not supported, 1 unsourced" })).toBeInTheDocument()
    expect(screen.getByText("Wrong (2)")).toBeInTheDocument()
    expect(screen.getByText("q01-k6-f1")).toBeInTheDocument()
  })

  it("score: a run without score.json says how to get one", async () => {
    renderRoutes(routes, "/runs/q01-on-s2?tab=score")
    expect(await screen.findByText("Not scored yet", {}, T)).toBeInTheDocument()
  })

  it("answer: a run that ended at the budget has no rows and says so", async () => {
    renderRoutes(routes, "/runs/q02-on-s1")
    expect(await screen.findByText("The run has no answer", {}, T)).toBeInTheDocument()
    expect(screen.getByText("exit status budget")).toBeInTheDocument()
  })
})

describe("jobs page", () => {
  it("lists jobs and selects one for its log", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/jobs")
    expect(await screen.findByText("Select a job to follow its log.", {}, T)).toBeInTheDocument()
    expect(screen.getAllByText("failed").length).toBeGreaterThan(0)
    await user.click(screen.getByRole("link", { name: "job-0006" }))
    expect(router.state.location.pathname).toBe("/jobs/job-0006")
    expect(await screen.findByRole("log", { name: "Log of job-0006" })).toBeInTheDocument()
  })
})
