/** The run page's tabs against the mock backend, and the jobs page. */
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { RUN } from "@/mocks/fixtures"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const runPath = (runId: string, tab?: string) => `/runs/${encodeURIComponent(runId)}${tab ? `?tab=${tab}` : ""}`

beforeAll(async () => {
  await Promise.all([import("@/pages/RunPage"), import("@/pages/JobsPage")])
}, 180_000)

describe("run page tabs", () => {
  it("header shows the run's stats against its budget", async () => {
    renderRoutes(routes, runPath(RUN.on))
    expect(await screen.findByRole("heading", { name: "q01-claim_on-r1-a1" }, T)).toBeInTheDocument()
    expect(screen.getByText("m4-72")).toBeInTheDocument()
    expect(screen.getByText("71.4K")).toBeInTheDocument()
    expect(screen.getByText("/ 2M")).toBeInTheDocument()
    expect(screen.getByText("/ 60")).toBeInTheDocument()
    expect(screen.getByText("verified")).toBeInTheDocument()
    expect(screen.getByText("submitted")).toBeInTheDocument()
  })

  it("header of a claim_off run shows the attach step and its cost", async () => {
    renderRoutes(routes, runPath(RUN.off))
    expect(await screen.findByText("attached", {}, T)).toBeInTheDocument()
    expect(screen.getByText("30.2K without attach")).toBeInTheDocument()
  })

  it("answer: a run that ended at the budget has no rows and says so", async () => {
    renderRoutes(routes, runPath(RUN.q02on))
    expect(await screen.findByText("The run has no answer", {}, T)).toBeInTheDocument()
    expect(screen.getByText("exit status budget")).toBeInTheDocument()
    expect(screen.getByText("provisional")).toBeInTheDocument() // scored against the draft key
  })

  it("answer: the legend counts the facts by the status scoring gave them", async () => {
    renderRoutes(routes, runPath(RUN.on))
    const legend = await screen.findByRole("list", { name: "Facts by support status" }, T)
    expect(legend).toHaveTextContent("3 supported")
    expect(legend).toHaveTextContent("1 partial")
    expect(legend).toHaveTextContent("1 unsourced")
    expect(screen.getByText(/partial counts as not supported/)).toBeInTheDocument()
  })

  it("graph: an empty graph says why", async () => {
    renderRoutes(routes, runPath(RUN.live, "graph"))
    expect(await screen.findByText("The graph is empty", {}, T)).toBeInTheDocument()
  })

  it("timeline: steps in order with sub-agent, claims, rejected reason and the budget", async () => {
    renderRoutes(routes, runPath(RUN.on, "timeline"))
    const steps = await screen.findByRole("list", { name: "Steps" }, T)
    expect(within(steps).getByText("Step 1")).toBeInTheDocument()
    expect(within(steps).getByText("Step 8")).toBeInTheDocument()
    expect(within(steps).getByText("sub-01")).toBeInTheDocument()
    expect(within(steps).getByText("not_found")).toBeInTheDocument()
    expect(within(steps).getByRole("separator", { name: "Phase research to conclude" })).toBeInTheDocument()
    expect(screen.getByText("Research steps")).toBeInTheDocument()
    expect(screen.getByText("of 60")).toBeInTheDocument()
  })

  it("timeline: a coverage notice explains itself", async () => {
    renderRoutes(routes, runPath(RUN.live, "timeline"))
    expect(await screen.findByText("coverage: unparsed", {}, T)).toBeInTheDocument()
    expect(screen.getByText(/The reply had no bash block/)).toBeInTheDocument()
  })

  it("timeline: the live run streams its remaining steps and finishes", async () => {
    renderRoutes(routes, runPath(RUN.live, "timeline"))
    const steps = await screen.findByRole("list", { name: "Steps" }, T)
    // the mock stream plays steps 4-6 (a claim, a rejected claim, the final answer), then done
    expect(await within(steps).findByText("Step 6", {}, T)).toBeInTheDocument()
    expect(await within(steps).findByText("final answer", {}, T)).toBeInTheDocument()
    expect(within(steps).getByRole("separator", { name: "Phase research to conclude" })).toBeInTheDocument()
    expect(await screen.findByText("finished", {}, T)).toBeInTheDocument()
  })

  it("timeline: the attach step's steps of a claim_off run", async () => {
    renderRoutes(routes, runPath(RUN.off, "timeline"))
    const steps = await screen.findByRole("list", { name: "Steps" }, T)
    expect(within(steps).getByRole("separator", { name: "Phase conclude to attach" })).toBeInTheDocument()
    expect(within(steps).getByText("coverage: no_source_found")).toBeInTheDocument()
  })

  it("claims: filter to the rejected ones and walk an accepted one", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, runPath(RUN.on, "claims"))
    const search = await screen.findByRole("searchbox", { name: "Search" }, T)
    const table = screen.getByRole("table")
    expect(within(table).getAllByRole("row")).toHaveLength(9) // header + 8 claims
    await user.type(search, "hellaswag")
    expect(within(table).getAllByRole("row")).toHaveLength(2)
    expect(within(table).getByText("not_found")).toBeInTheDocument()
    await user.clear(search)
    await user.click(within(table).getByRole("button", { name: "Walk claim-000006" }))
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText(/no answer fact cites it/)).toBeInTheDocument()
  })

  it("provenance: runs a query and a SPARQL query", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, runPath(RUN.on, "provenance"))
    await user.click(await screen.findByRole("button", { name: "Run query 5" }, T))
    const result = await screen.findByRole("table", { name: "Query 5 results" })
    expect(within(result).getByText("HellaSwag")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Run query 3" }))
    expect(await screen.findByText("query 3 needs a step, an agent, or both")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Run" }))
    expect(await screen.findByText("7 rows")).toBeInTheDocument()
  })

  it("score: the support breakdown and the facts against the key", async () => {
    renderRoutes(routes, runPath(RUN.on, "score"))
    expect(await screen.findByText("60.0%", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "3 supported, 1 partial, 0 not supported, 1 unsourced" })).toBeInTheDocument()
    const missed = screen.getByRole("region", { name: "Missed facts" })
    expect(within(missed).getByText(/q01-k6-f1/)).toBeInTheDocument()
    expect(within(screen.getByRole("region", { name: "Extra facts" })).getByText(/HellaSwag/)).toBeInTheDocument()
    expect(screen.getByText("Matched (4)")).toBeInTheDocument()
  })

  it("score: a run without score.json says how to get one", async () => {
    renderRoutes(routes, runPath(RUN.live, "score"))
    expect(await screen.findByText("Not scored yet", {}, T)).toBeInTheDocument()
  })
})

describe("jobs page", () => {
  it("lists jobs and selects one for its steps and log", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/jobs")
    expect(await screen.findByText("Select a job to follow its steps and log.", {}, T)).toBeInTheDocument()
    expect(screen.getAllByText("failed").length).toBeGreaterThan(0)
    await user.click(screen.getByRole("link", { name: "job-0006" }))
    expect(router.state.location.pathname).toBe("/jobs/job-0006")
    expect(await screen.findByRole("log", { name: "Log of job-0006" })).toBeInTheDocument()
    const steps = await screen.findByRole("list", { name: "Steps of the job" })
    expect(within(steps).getAllByRole("listitem")).toHaveLength(7)
    expect(await screen.findByText("score: support share 0.50, fact F1 0.67", {}, T)).toBeInTheDocument()
  })

  it("cancels a running job", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/jobs/job-0007")
    await user.click(await screen.findByRole("button", { name: "Cancel" }, T))
    expect(await screen.findByText("cancelled", {}, T)).toBeInTheDocument()
  })
})
