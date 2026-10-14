/** Smoke tests of the pages against the mock backend: each renders its data, its empty or its error state. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { GOLD, initialRunDetails, RUN } from "@/mocks/fixtures"
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
    const table = await screen.findByRole("table", { name: "Questions and their pipeline state" }, T)
    expect(within(table).getAllByRole("row")).toHaveLength(13)
    expect(within(table).getByText("Which paper in this corpus is the most influential?")).toBeInTheDocument()
    expect(await screen.findByText("1 of 12", {}, T)).toBeInTheDocument() // gold keys reviewed
    expect(within(table).getByRole("link", { name: "Runs of q01" })).toHaveTextContent("2 / 1")
  })

  it("question page shows the briefs side by side and records a pick", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/questions/q07")
    const briefs = await screen.findByRole("list", { name: "Concept briefs" }, T)
    expect(briefs.querySelectorAll(":scope > [role=listitem]")).toHaveLength(3)
    expect(within(briefs).getAllByRole("button", { name: /^Pick brief \d$/ })).toHaveLength(3)
    expect(within(briefs).getByRole("figure", { name: "Answer shape: graph" })).toBeInTheDocument()
    expect(screen.getByText("No brief is picked yet. Compare the briefs and pick the one that makes the question answerable.")).toBeInTheDocument()
    const bodies: unknown[] = []
    server.events.on("request:start", ({ request }) => {
      if (request.method === "POST" && request.url.endsWith("/concepts/pick")) void request.clone().json().then((b) => bodies.push(b))
    })
    await user.click(screen.getByRole("button", { name: "Pick brief 2" }))
    const dialog = await screen.findByRole("dialog")
    // the browser records only the user's own pick: no "picked by" choice
    expect(within(dialog).queryByRole("combobox")).not.toBeInTheDocument()
    await user.type(within(dialog).getByLabelText("Reason"), "pairwise comparisons answer 'best'")
    await user.click(within(dialog).getByRole("button", { name: "Record the pick" }))
    expect(await screen.findByRole("button", { name: "Picked" }, T)).toBeDisabled()
    expect(screen.getByText(/picked by user/)).toBeInTheDocument()
    await waitFor(() => expect(bodies).toEqual([expect.objectContaining({ choice: 2, picked_by: "user" })]))
    server.events.removeAllListeners("request:start")
    // now picked, the question offers its gold build
    expect(screen.getByRole("button", { name: /Build the gold standard/ })).toBeEnabled()
  })

  it("question page offers to propose when there are no briefs, and starts the job", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/questions/q05")
    expect(await screen.findByText("No concept briefs yet", {}, T)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Propose concepts" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Start" }))
    expect(await screen.findByText(/Proposing concepts for q05: job job-0008/, {}, T)).toBeInTheDocument()
  })

  it("question page: a pick the gold build depends on cannot change", async () => {
    renderRoutes(routes, "/questions/q01")
    const briefs = await screen.findByRole("list", { name: "Concept briefs" }, T)
    expect(within(briefs).getByRole("button", { name: "Picked" })).toBeDisabled()
    expect(within(briefs).getByRole("button", { name: "Change the pick to brief 1" })).toBeDisabled()
    expect(screen.getByText(/it can no longer change/)).toBeInTheDocument()
  })

  it("runs page filters by condition through the URL", async () => {
    const { router } = renderRoutes(routes, "/runs?condition=claim_off")
    expect(await screen.findByText("q01-claim_off-r1-a1", {}, T)).toBeInTheDocument()
    expect(screen.queryByText("q01-claim_on-r1-a1")).not.toBeInTheDocument()
    expect(screen.getAllByText("m4-72").length).toBeGreaterThan(0) // the batch
    expect(router.state.location.search).toBe("?condition=claim_off")
  })

  it("runs page has an empty state for filters that match nothing", async () => {
    renderRoutes(routes, "/runs?qid=q12")
    expect(await screen.findByText("No runs match these filters", {}, T)).toBeInTheDocument()
  })

  it("new run dialog starts both conditions with one seed", async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    server.events.on("request:start", ({ request }) => {
      if (request.method === "POST" && new URL(request.url).pathname === "/api/runs") void request.clone().json().then((b) => bodies.push(b))
    })
    renderRoutes(routes, "/runs?qid=q01")
    await user.click(await screen.findByRole("button", { name: "New run" }, T))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("combobox", { name: "Condition" }))
    await user.click(await screen.findByRole("option", { name: "both, same seed" }))
    const seed = within(dialog).getByLabelText("Seed")
    await user.clear(seed)
    await user.type(seed, "4")
    await user.click(within(dialog).getByRole("button", { name: "Start both runs" }))
    expect(await screen.findByText(/Started 2 runs/, {}, T)).toBeInTheDocument()
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies).toEqual([
      expect.objectContaining({ qid: "q01", condition: "claim_on", seed: 4, attach: false, force: false, steps: null }),
      expect.objectContaining({ qid: "q01", condition: "claim_off", seed: 4, attach: true }),
    ])
    server.events.removeAllListeners("request:start")
  })

  it("new run dialog asks for an explicit yes before an unsandboxed run, and such runs are marked", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/runs?qid=q07")
    // the q07 run in the fixtures ran unsandboxed: the table says so
    expect(await screen.findByText("unsandboxed", {}, T)).toBeInTheDocument()
    await user.click(screen.getAllByRole("button", { name: "New run" })[0])
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("combobox", { name: "Question" }))
    await user.click(await screen.findByRole("option", { name: /q01/ }))
    await user.click(within(dialog).getByRole("combobox", { name: "Sandbox" }))
    await user.click(await screen.findByRole("option", { name: "unsandboxed (tests only)" }))
    expect(within(dialog).getByText("Unsandboxed is for tests only")).toBeInTheDocument()
    const start = within(dialog).getByRole("button", { name: "Start run" })
    expect(start).toBeDisabled()
    await user.click(within(dialog).getByRole("switch", { name: "Run it without the sandbox" }))
    expect(start).toBeEnabled()
  })

  it("new run dialog offers to start anyway when a cluster batch is live", async () => {
    const user = userEvent.setup()
    const forced: boolean[] = []
    server.use(http.post("/api/runs", async ({ request }) => {
      const body = (await request.json()) as { force?: boolean }
      forced.push(!!body.force)
      return body.force
        ? HttpResponse.json({ id: "job-0099", kind: "run", args: body, state: "queued", created_at: "2026-10-13T09:00:00Z", run_id: null }, { status: 202 })
        : HttpResponse.json({ detail: "2 run(s) the web app did not start are live (m4-72~q03-claim_on-r1-a1, m4-72~q03-claim_off-r1-a1): a batch shares the orchestrator; set force to start anyway" }, { status: 409 })
    }))
    renderRoutes(routes, "/runs?qid=q01")
    await user.click(await screen.findByRole("button", { name: "New run" }, T))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Start run" }))
    expect(await within(dialog).findByText(/a batch shares the orchestrator/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Start anyway" }))
    expect(await screen.findByText(/Started a run: job job-0099/, {}, T)).toBeInTheDocument()
    expect(forced).toEqual([false, true])
  })

  it("run page 404 says there is no such run", async () => {
    renderRoutes(routes, "/runs/nope")
    expect(await screen.findByText("No run nope", {}, T)).toBeInTheDocument()
  })

  it("run page of a run its job has not written yet waits for it, then opens it", async () => {
    let written = false
    const job = {
      id: "job-0042", kind: "run", args: {}, state: "running", created_at: "2026-10-14T09:00:00Z", run_id: "web~fresh",
      steps: [{ name: "run", argv: [], command: "agent run", state: "running" }, { name: "verify", argv: [], command: "agent verify", state: "pending" }],
    }
    server.use(
      http.get("/api/jobs", () => HttpResponse.json([job])),
      http.get("/api/runs/web~fresh", () =>
        written ? HttpResponse.json(initialRunDetails()[RUN.on]) : HttpResponse.json({ detail: "no run" }, { status: 404 })),
    )
    renderRoutes(routes, "/runs/web~fresh")
    expect(await screen.findByText("Starting run web~fresh", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("list", { name: "Job steps" })).toHaveTextContent("verify")
    expect(screen.getByRole("link", { name: "Job log" })).toHaveAttribute("href", "/jobs/job-0042")
    expect(screen.queryByText(/No run web~fresh/)).not.toBeInTheDocument()
    written = true // agent run has written config.json: the next poll opens the run
    await waitFor(() => expect(screen.queryByText("Starting run web~fresh")).not.toBeInTheDocument(), T)
    expect(await screen.findByRole("tab", { name: "Answer" }, T)).toBeInTheDocument()
  })

  it("results page shows the primary test, its sensitivity analyses and the per-question table", async () => {
    renderRoutes(routes, "/results")
    const primary = (await screen.findByText("Pre-registered primary outcome", {}, T)).closest<HTMLElement>("[data-slot=card]")!
    expect(within(primary).getAllByText("+19.0 pp")[0]).toHaveClass("text-4xl") // the estimate, before the sensitivity rows
    expect(within(primary).getByText("95% BCa interval [+16.0 pp, +21.0 pp]")).toBeInTheDocument()
    expect(within(primary).getByText("significant at α = 0.05")).toBeInTheDocument()
    expect(within(primary).getAllByText("< 0.001").length).toBeGreaterThan(0)
    expect(within(primary).getByText("each fact judged by its first cited claim only")).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Support share by condition" })).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Difference in support share per question" })).toBeInTheDocument()
    const secondary = screen.getByRole("table", { name: "Secondary outcomes by condition" })
    expect(within(secondary).getByRole("columnheader", { name: "Paired questions" })).toBeInTheDocument()
    expect(within(secondary).getAllByText("36 / 36").length).toBeGreaterThan(0) // runs on / off behind each mean
    const perQuestion = screen.getByRole("table", { name: "Outcomes per question and condition" })
    expect(within(perQuestion).getAllByRole("row")).toHaveLength(13)
  })

  it("results page warns when the numbers are provisional or the test is not computed", async () => {
    server.use(http.get("/api/results", () => HttpResponse.json({
      provisional: true, provisional_runs: 6, complete: false, completeness: { pending_support_runs: ["m4-72~q01-claim_on-r1-a1"] },
      primary: {
        outcome: "support_share", test: "wilcoxon signed-rank", alternative: "two-sided", alpha: 0.05, n_pairs: 2, n_nonzero: 2, computed: false,
        reason: "fewer than 6 paired questions (n = 2)", statistic: null, p_value: null, significant: null, rank_biserial: null,
        mean_difference: 0.1, ci_low: null, ci_high: null, ci_method: "none (fewer than 2 questions)", questions: ["q01", "q02"], excluded_questions: [],
      },
    })))
    renderRoutes(routes, "/results")
    expect(await screen.findByText("Provisional", {}, T)).toBeInTheDocument()
    expect(screen.getByText("Judge verdicts pending")).toBeInTheDocument()
    expect(screen.getByText("not computed")).toBeInTheDocument()
    expect(screen.getByText(/fewer than 6 paired questions/)).toBeInTheDocument()
  })

  it("results page shows every warning report.md has: judge calibration, verify failures, settings, duplicates", async () => {
    server.use(http.get("/api/results", () => HttpResponse.json({
      provisional: true, provisional_runs: 2, complete: true,
      completeness: { verify_failed_runs: ["m4-72~q02-claim_off-r1-a1"], key_problem_runs: [], key_states: { incomplete: 2, reviewed: 70 },
                      settings_differ: { loop: { a: 1, b: 71 } }, partial_counts_as: { no: 72 }, support_context: { calibrated: 72 } },
      judge: { state: "failed", validated: false, kappa: [0.48], bar: 0.61 },
      duplicates: [{ run_id: "q01-claim_on-r1-a1", qid: "q01", condition: "claim_on", repeat: 1, attempt: 1 }],
      coverage: { claim_on: { scored: 36, answered: 30, answered_share: 0.83, not_scored: 0 }, claim_off: { scored: 35, answered: 30, answered_share: 0.86, not_scored: 1 } },
      primary: {
        outcome: "support_share", test: "wilcoxon signed-rank", alternative: "two-sided", alpha: 0.05, n_pairs: 12, n_nonzero: 12, computed: true,
        reason: null, statistic: 3, p_value: 0.002, significant: true, rank_biserial: 0.9, mean_difference: 0.2, ci_low: 0.1, ci_high: 0.3,
        ci_method: "BCa", questions: [], excluded_questions: [], judge_validated: false, judge_calibration: "failed",
      },
    })))
    renderRoutes(routes, "/results")
    expect(await screen.findByText("The judge failed its calibration", {}, T)).toBeInTheDocument()
    expect(screen.getByText(/Kappa 0.48 is below the bar of 0.61/)).toBeInTheDocument()
    expect(screen.getByText("unvalidated: judge failed calibration")).toBeInTheDocument()
    expect(screen.getByText(/2 against a key whose review is not finished/)).toBeInTheDocument()
    expect(screen.getByText("Duplicate runs left out")).toBeInTheDocument()
    expect(screen.getByText(/1 scored runs failed `agent verify`/)).toBeInTheDocument()
    expect(screen.getByText(/Settings differ between runs: loop/)).toBeInTheDocument()
    expect(screen.getByText(/1 planned runs were not scored/)).toBeInTheDocument()
  })

  it("results page explains a missing report", async () => {
    server.use(http.get("/api/results", () => HttpResponse.json({ detail: "no report" }, { status: 404 })))
    renderRoutes(routes, "/results")
    expect(await screen.findByText("No report yet", {}, T)).toBeInTheDocument()
  })

  it("gold page shows kappa, review progress and the key", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/gold")
    expect(await screen.findByText("0.81", {}, T)).toBeInTheDocument()
    expect(screen.getByText("155 of 155 decided")).toBeInTheDocument()
    expect(screen.getByText("37 of 98 decided · 2 disagreements")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Open Argilla/ })).toHaveAttribute("href", "http://127.0.0.1:26900")
    await user.click(screen.getAllByRole("button", { name: "Key" })[0])
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText("q01-k6-f1")).toBeInTheDocument()
  })

  it("gold page shows κ with its interval, and says when the overlap was not independent", async () => {
    server.use(http.get("/api/gold", () => HttpResponse.json([
      {
        ...GOLD[0],
        report: {
          ...(GOLD[0].report as object),
          kappa: {
            items: 31, keep: { items: 31, kappa: 0.7, kappa_95: [0.41, 0.88] }, bar: 0.61, keep_kappa_meets_bar: true, independent: false,
            warning: "overlap records from the last pull, not the independent round",
          },
        },
      },
    ])))
    renderRoutes(routes, "/gold")
    expect(await screen.findByText("0.70", {}, T)).toBeInTheDocument()
    expect(screen.getByText("[0.41, 0.88]")).toBeInTheDocument()
    expect(screen.getByText("overlap records from the last pull, not the independent round")).toBeInTheDocument()
  })

  it("gold page and question page offer to run a stopped gold build again", async () => {
    const user = userEvent.setup()
    const stopped = { qid: "q01", status: "building", stage: "failed", key_version: null, rows: null, facts: null, coverage: null, counts: null, report: null }
    server.use(
      http.get("/api/gold", () => HttpResponse.json([stopped])),
      http.get("/api/jobs", () => HttpResponse.json([])),
    )
    renderRoutes(routes, "/gold")
    expect(await screen.findByText("the build stopped; run it again", {}, T)).toBeInTheDocument()
    await user.click(await screen.findByRole("button", { name: "Run the gold build of q01 again" }, T))
    expect(await screen.findByText(/Building the gold standard of q01/, {}, T)).toBeInTheDocument()
  })

  it("compare page puts both conditions side by side with the differences", async () => {
    renderRoutes(routes, "/compare/q01")
    expect(await screen.findByText("claim on minus claim off", {}, T)).toBeInTheDocument()
    expect(screen.getByText("+10.0 pp")).toBeInTheDocument() // support share 0.6 vs 0.5
    expect(await screen.findByRole("list", { name: `Answer of ${RUN.on}` }, T)).toBeInTheDocument()
    expect(screen.getByRole("list", { name: `Answer of ${RUN.off}` })).toBeInTheDocument()
  })

  it("overview says when the runs or the report could not be loaded, rather than 'nothing scored'", async () => {
    server.use(
      http.get("/api/runs", () => HttpResponse.json({ detail: "runs root unreadable" }, { status: 500 })),
      http.get("/api/results", () => HttpResponse.json({ detail: "report.json is not JSON" }, { status: 500 })),
    )
    renderRoutes(routes, "/")
    expect(await screen.findByText(/Could not load the runs/, {}, T)).toBeInTheDocument()
    expect(screen.getByText(/Could not load the report/)).toBeInTheDocument()
    expect(screen.getByText("runs root unreadable")).toBeInTheDocument()
    expect(screen.queryByText(/0 of 72/)).not.toBeInTheDocument()
    expect(screen.queryByText("not yet")).not.toBeInTheDocument()
    expect(screen.getAllByText("not loaded").length).toBeGreaterThan(2) // two tiles and the support column
  })

  it("answer tab and compare say when score.json failed, rather than 'not scored yet'", async () => {
    server.use(http.get("/api/runs/:run/score", () => HttpResponse.json({ detail: "score.json is not JSON" }, { status: 500 })))
    renderRoutes(routes, `/runs/${encodeURIComponent(RUN.on)}`)
    expect(await screen.findByText("Could not load score.json", { exact: false }, T)).toBeInTheDocument()
    expect(screen.getByText(/The verdicts could not be loaded/)).toBeInTheDocument()
    expect(screen.queryByText(/Not scored yet/)).not.toBeInTheDocument()
  })

  it("compare says when a score failed to load", async () => {
    server.use(http.get("/api/runs/:run/score", () => HttpResponse.json({ detail: "score.json is not JSON" }, { status: 500 })))
    renderRoutes(routes, "/compare/q01")
    expect(await screen.findByText(/Could not load the scores to compare/, {}, T)).toBeInTheDocument()
    expect(screen.queryByText(/The differences appear when both runs are scored/)).not.toBeInTheDocument()
  })

  it("an API error shows the backend's reason and a retry", async () => {
    server.use(http.get("/api/gold", () => HttpResponse.json({ detail: "gold root missing" }, { status: 500 })))
    renderRoutes(routes, "/gold")
    const alert = await screen.findByRole("alert", {}, T)
    expect(alert).toHaveTextContent("gold root missing")
    expect(within(alert).getByRole("button", { name: /Try again/ })).toBeInTheDocument()
  })
})
