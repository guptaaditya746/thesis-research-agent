---
name: tim
description: Predict how Tim (Aditya's thesis supervisor) would likely judge an idea, design choice or result, based only on what he has said so far; quotes his words, separates what he said from inference, and drafts a question to send him when his feedback does not cover it. Use when the user types /tim or asks "what would Tim say/think".
---

# /tim: what would Tim think?

Tim is the supervisor of Aditya's master's thesis. His feedback so far is in `feedback.md` next to this file
(verbatim, two written messages of 14 Oct 2026) plus the "Reported, not written" points below. Read
`feedback.md` in full before answering; never answer from memory of it.

## How to answer

Given the user's idea, design choice, result or question (the text after `/tim`, or the current topic):

1. **Likely view**: one or two sentences: welcome / fine / neutral / likely to object / not covered.
2. **Why, in his words**: quote the sentences that bear on it, with their place (M1, or M2 §1–§9). Only
   quote what is in `feedback.md` or listed below; never paraphrase a quote or invent one.
3. **Stated vs inferred**: say plainly which part he said and which part is your inference. If he said
   nothing on it, say "not covered" — do not fill the gap with a guess dressed as his view.
4. **Fit with his scope**: does it serve his §8 order (manual protocol → generator → extractors →
   representation → rules → separate A/B/C evaluation → answer-level baseline) or the core of §9, or is it an
   extension? He marked LLM protocol generation and real papers as optional ("I would not make either of
   these extensions a requirement").
5. **Risks he would raise**: e.g. scope creep away from "a complete vertical slice", assuming the
   evidence-level approach wins ("We should not assume…"), weak fidelity of synthetic papers, an unfair
   baseline, extraction and synthesis errors not kept apart.
6. **Question to send him** (when not covered or contested): a short, neutral draft in plain English that
   Aditya can paste into an email — one question, the options, what we would do by default.

Keep it short. Our own additions (agentic extractor, agent baseline, locate step, cascade/funnel engine,
provenance and replay lane, record cache, re-execution, PROV-O, proposal flow with choice points, critic,
vocabulary snapshot, amendments) are ours, not his: never attribute them to him; judge them against what he
wrote.

## Reported, not written (from Aditya; treat as his view but cite as "reported by Aditya")

- 16 Oct 2026: Tim's motivation for provenance: a search engine or chatbot gives an answer like a calculator
  gives the result of a maths problem, without the steps, so users cannot check it and trust it less.
  (Not in his written messages; wording is Aditya's.)
- 2 Nov 2026: Tim does not like a pilot run (running the plan on a few papers first to fix it before the full
  run). For him it is okay for the system to return an empty answer. (Wording is Aditya's.)
- 2 Nov 2026: Tim wants a human involved in planning the question (the protocol), not a fully automatic plan.
  (Wording is Aditya's.)

When the user reports a new point from Tim (meeting, email), add it to this list with the date, or append a
new written message verbatim to `feedback.md`, and say that you did.
