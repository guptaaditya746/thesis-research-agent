/** MSW answers for the system API (/api/ev/system, webapp/evsystem.py), so `npm run dev:mock` shows the page. */
import { http, HttpResponse } from "msw"

import type { SystemDomain, SystemSteps } from "@/routes/system/api"

const domains: SystemDomain[] = [
  {
    domain: "demo", seeds: [1], error: null,
    questions: [
      { id: "d01", question: "Does Targeted therapy change the Response rate?", sub_questions: ["Is it faster?"], kind: "effect", target: null, plan: "missing" },
      { id: "d02", question: "Which conditions were studied?", sub_questions: ["Which are the oldest?", "Which have the most papers?"], kind: "inventory", target: "condition", plan: "missing" },
      { id: "d03", question: "What is known about Response rate?", sub_questions: [], kind: "written", target: null, plan: "missing" },
    ],
  },
]

const steps: SystemSteps = {
  status: "done", answer_by: "written", question: "Does Targeted therapy change the Response rate?", program_refused: null,
  find: { count: 1, papers: [{ paper: "S001", kept: true, why: "kept by the screen" }] },
  pull: { count: 1, left_out: 0, facts: [{ n: 1, item: "S001:r1", paper: "S001", type: "result", text: "Response rate 0.4 against 0.3." }] },
  combine: { rule: "A model wrote the answer from the facts.", count: 1, rows: [{ text: "Targeted therapy does better.", facts: [1] }] },
  answer: { text: "Targeted therapy does better.", status: "ok", problems: [], lines: [{ text: "Targeted therapy does better.", facts: [1] }] },
}

export const systemHandlers = [
  http.get("/api/ev/system/domains", () => HttpResponse.json(domains)),
  http.get("/api/ev/system/runs/:rid/steps", () => HttpResponse.json(steps)),
  http.get("/api/ev/system/runs/:rid/papers/:doc", ({ params }) =>
    HttpResponse.json({ paper: String(params.doc), text: "Response rate 0.4 against 0.3.", segments: [{ text: "Response rate 0.4 against 0.3.", start: 0, end: 30, marks: ["S001:r1"], roles: [] }] })),
]
