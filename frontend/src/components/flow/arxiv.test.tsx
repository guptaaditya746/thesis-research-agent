/** "Fetch from arXiv" against the mock backend: the dialog starts the job, the corpus it leaves is listed as a
 * demonstration (no ground truth), and no run on it is scored. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { evApi, type CorpusSummary, type Job } from "@/api/ev"
import { routes } from "@/app/routes"
import { evFixture } from "@/mocks/ev"
import { fetchName, finishJob } from "@/mocks/handlers"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const MIXED = "rag-tpl-w1-mixed"

beforeAll(async () => {
  await Promise.all([import("@/pages/ev/CorporaPage"), import("@/pages/flow/FlowPage")])
}, 180_000)

afterEach(() => server.events.removeAllListeners())

/** The bodies POST /api/ev/jobs/fetch got. */
function recordFetches() {
  const bodies: unknown[] = []
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "POST" && new URL(request.url).pathname === "/api/ev/jobs/fetch") bodies.push(await request.clone().json())
  })
  return bodies
}

async function fillDialog(user: ReturnType<typeof userEvent.setup>, query: string, papers: string, category: string) {
  await user.click(await screen.findByRole("button", { name: "Fetch from arXiv" }, T))
  const dialog = await screen.findByRole("dialog", { name: "Fetch real papers from arXiv" })
  await user.type(within(dialog).getByLabelText("Search words"), query)
  await user.clear(within(dialog).getByLabelText("Papers"))
  await user.type(within(dialog).getByLabelText("Papers"), papers)
  if (category) await user.type(within(dialog).getByLabelText("Category (optional)"), category)
  return dialog
}

describe("fetch from arXiv", () => {
  it("starts the job from the Corpora page and lists the corpus as a demo once it ends", async () => {
    const user = userEvent.setup()
    const bodies = recordFetches()
    renderRoutes(routes, "/corpora")
    const dialog = await fillDialog(user, "retrieval augmented generation", "3", "cs.CL")
    expect(within(dialog).getByText(/real papers have no ground truth/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Fetch papers" }))
    await waitFor(() => expect(bodies).toEqual([{ query: "retrieval augmented generation", max_papers: 3, category: "cs.CL", name: null }]))
    const name = fetchName("retrieval augmented generation", new Date())
    expect(await screen.findByText(`arXiv corpus ${name}`, {}, T)).toBeInTheDocument()   // the job's progress
    const [job] = await evApi.jobs()
    finishJob(job.id)
    const table = await screen.findByRole("table", { name: "Corpora" }, T)
    const row = (await within(table).findByRole("link", { name: name }, T)).closest("tr") as HTMLElement
    expect(within(row).getByText("real papers, not scored here")).toBeInTheDocument()
    expect(within(table).getAllByText("real papers, not scored here")).toHaveLength(1)   // the synthetic corpora have none
  })

  it("refuses a bad category in the dialog", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/corpora")
    const dialog = await fillDialog(user, "retrieval", "3", "cs.CL; rm")
    expect(within(dialog).getByRole("button", { name: "Fetch papers" })).toBeDisabled()
    expect(within(dialog).getByLabelText("Category (optional)")).toHaveAttribute("aria-invalid", "true")
  })

  it("chooses the corpus being fetched in the flow's corpus step", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/flow/rag-factuality/corpus")
    const dialog = await fillDialog(user, "dense retrieval", "2", "")
    await user.click(within(dialog).getByRole("button", { name: "Fetch papers" }))
    const name = fetchName("dense retrieval", new Date())
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("corpus")).toBe(name))
    expect(await screen.findByText(`arXiv corpus ${name}`, {}, T)).toBeInTheDocument()
  })

  it("shows no Score for a run on a demonstration corpus, and the mock refuses it as the backend does", async () => {
    const corpora = evFixture<CorpusSummary[]>("/api/ev/corpora")
    server.use(http.get("/api/ev/corpora", () => HttpResponse.json(corpora.map((c) => (c.name === MIXED ? { ...c, ground_truth: false } : c)))))
    renderRoutes(routes, `/flow/rag-factuality/run?corpus=${MIXED}`)
    const runs = await screen.findByRole("table", { name: "Runs on the corpus" }, T)
    expect(await screen.findByText(/Real papers, not scored here:/, {}, T)).toBeInTheDocument()
    expect(within(runs).queryByRole("button", { name: /^Score / })).toBeNull()
    expect(screen.queryByRole("button", { name: "Compare the scored runs" })).toBeNull()

    const fetched: Job = await evApi.startJob("fetch", { query: "retrieval", max_papers: 2, category: null, name: "arxiv-demo" })
    finishJob(fetched.id)
    const run = await evApi.startJob("run", { corpus: "arxiv-demo", protocol: { source: "repo", name: "rag-factuality" }, extractors: "regex-only", strategy: "all", model: "orch-model", group: null, name: null, retry_errors: false })
    finishJob(run.id)
    await expect(evApi.startJob("score", { run: run.refs.run })).rejects.toThrow(/is not scored here: real papers/)
  })
})
