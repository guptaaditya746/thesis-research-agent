/** MSW answers for the review API (/api/ev/review, webapp/evreview.py), so `npm run dev:mock` shows the page. */
import { http, HttpResponse } from "msw"

const world = { seed: 1, approved: false, text: "World of demo, seed 1\n\n  arm            measure   value\n  Standard care  Response  0.30\n  Targeted       Response  0.40", path: "worlds/demo/s1.json" }

export const reviewHandlers = [
  http.get("/api/ev/review", () => HttpResponse.json({ domains: [{ domain: "demo", questions: 3, seeds: [1], worlds: [1] }] })),
  http.get("/api/ev/review/judge-test", () => HttpResponse.json([{ n: 0, domain: "demo", seed: 1, question_id: "d01", done: false }])),
  http.get("/api/ev/review/judge-test/:n", () =>
    HttpResponse.json({
      n: 0, domain: "demo", seed: 1, question_id: "d01", question: "Does Targeted therapy change the Response rate?",
      answer: "Targeted therapy does better.", points: [{ id: "p1", text: "Targeted therapy does better." }],
      facts: [{ n: 1, paper: "S001", quote: "Response rate 0.4 against 0.3." }], facts_cut: false, marked: null,
    })),
  http.put("/api/ev/review/judge-test/:n", async ({ request }) => HttpResponse.json({ by: "mock", ...((await request.json()) as object) })),
  http.get("/api/ev/review/:domain/worlds", () => HttpResponse.json([world])),
  http.put("/api/ev/review/:domain/worlds/:seed", async ({ request }) =>
    HttpResponse.json({ ...world, approved: ((await request.json()) as { approved: boolean }).approved })),
  http.get("/api/ev/review/:domain/sheets", () =>
    HttpResponse.json([
      { seed: 1, question_id: "d01", status: "drafted", stale: null, must_check: "full" },
      { seed: 1, question_id: "d02", status: "missing", stale: null, must_check: "full" },
    ])),
  http.get("/api/ev/review/:domain/sheets/:seed/:qid", ({ params }) =>
    HttpResponse.json({
      question: "Does Targeted therapy change the Response rate?", sub_questions: ["Is it faster?"],
      scope: { arms: ["Targeted therapy", "Standard care"], measures: [], conditions: [], settings: [] },
      facts: [{ id: "pair:a:m1", text: "Response rate: 0.4 vs 0.3" }],
      sheet: params.qid === "d02" ? null : { status: "drafted", points: [{ id: "p1", text: "Targeted therapy does better.", facts: ["pair:a:m1"] }], warnings: [], checked_by: null },
      stale: null,
    })),
  http.put("/api/ev/review/:domain/sheets/:seed/:qid", () => HttpResponse.json({ status: "checked" })),
]
