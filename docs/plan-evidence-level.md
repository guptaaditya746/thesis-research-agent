# Plan: evidence-level research with an explicit evidence plan (draft, 14 Oct 2026)

> **Superseded** by the supervisor's second message of 14 Oct (protocol, extractor library, synthetic
> benchmark), which is built: see [`evidence-interfaces.md`](evidence-interfaces.md). Kept for the record.

Draft for discussion with the supervisor before any code changes. It replaces the framing in
`docs/STATE.md` ("one contribution: provenance recorded while the agent researches") with the
supervisor's direction of 14 Oct, and keeps everything already built that still serves it.

## 1. Direction

A research question can be answered in two ways:

- **Answer-level**: find statements in the literature that already answer the question
  ("X is the most influential paper on RAG") and aggregate them.
- **Evidence-level**: decide what evidence would answer the question independently, extract that
  evidence from the papers, and synthesise the answer from it, even when no paper states the answer.

Existing assessments can be one kind of evidence; the difference is that evidence-level reasoning
does not depend on finding one.

The thesis builds a prototype that works evidence-level:

1. **Plan**: turn the question into an explicit **evidence plan**: which evidence, from which papers,
   which fields to extract, and how the evidence becomes the answer. The model proposes up to 3 plans,
   the user picks one (no editing), and the pick is frozen and hashed, like a systematic-review protocol.
2. **Extract**: one agent follows the plan through the corpus and records each piece of evidence with
   an exact quote as it finds it (the `claim` tool and broker that exist).
3. **Synthesise**: the agent derives the answer from the evidence by the plan's rule; each conclusion
   names the evidence it was derived from.

The evaluation focuses on step 2: **how reliably and how comprehensively the evidence the plan asks
for is extracted from the corpus**, measured against a gold evidence set built from the whole corpus
and reviewed by people.

One agent only: no subagents (the `spawn` command stays off; see section 7).

## 2. Research questions (proposal)

- **RQ1 (main): extraction quality.** Given a frozen evidence plan, how reliably and how
  comprehensively does the agent extract the evidence the plan asks for from the corpus?
  - Reliability: **support share**, the share of extracted facts whose quote supports them
    (judge, calibrated against people).
  - Comprehensiveness: **evidence recall**, the share of gold evidence facts the agent found (and
    vital recall, row recall).
  - Reported per question and per requirement, with BCa intervals over questions. No comparison is
    needed: this is a measurement of the system.
- No comparison between evidence-level and answer-level agents (decided 14 Oct, D3): the supervisor
  asks to evaluate components, not to compare the two. What papers already say about the answer
  (answer-level evidence, e.g. "X is seminal") is one kind of requirement inside a plan, as the
  supervisor describes ("existing assessments can also be considered as evidence").
- **RQ2 (optional): the plan itself.** Is the plan reproducible? Agreement between the plans the model
  proposes for one question under different seeds (same requirements?).

The old RQ1 (claim while researching vs attach afterwards) is **dropped completely** (decided 14 Oct):
recording each fact with a quote while researching is simply how the system works, not a condition.
No claim_off runs, no attach step.

## 3. The evidence plan

It replaces the concept brief (`agent/schemas/concept.schema.json`), which already has `definition`,
`measure`, `scope`, `answer_shape` and `competency_questions`. New or changed fields:

| Field | Meaning |
|---|---|
| `question`, `interpretation` | the question and how the plan reads it (what "influential" means here) |
| `requirements[]` | the evidence to collect, each with: `id`, `what` (one sentence), `why` (how it bears on the answer), `where` (sections or kinds of papers to look in), `include` / `exclude` criteria, `fields` (typed columns to extract, as answer_shape columns now) |
| `synthesis` | how evidence becomes the answer: the operation (count, rank, compare, list), its inputs (requirement ids and fields), tie-breaks, and what the answer is when evidence is missing |
| `answer_shape` | the shape of the final answer (kept) |
| `limits` | what the corpus cannot show (e.g. citations from outside the corpus) |
| `provenance` | who proposed, who edited what, when it was frozen; `plan.sha256` as `concept.sha256` now |

The user's part (decided 14 Oct): the model proposes up to 3 plans; the user **picks one, without
editing it**; the pick is recorded (who, when, why) and writes `plan.json` and its hash. Runs and gold
are built for a picked plan hash only (as for the concept hash now). So every plan in the experiment
is a model's plan, chosen but not rewritten by a person.

### Worked example: q08 "Which paper in this corpus is the most influential?"

- Interpretation: influence **within this corpus**: how much the other corpus papers build on a paper.
- Requirements:
  - **R1 citations**: for each corpus paper, which other corpus papers cite it. Where: reference lists.
    Fields: `cited_paper`, `citing_paper`.
  - **R2 reuse**: a corpus paper using another corpus paper's dataset, benchmark, method or code.
    Where: experiments, setup. Fields: `reused_paper`, `reusing_paper`, `what_is_reused`.
  - **R3 stated assessments**: statements calling a corpus paper seminal, foundational, widely used.
    Fields: `paper`, `assessment`. (Answer-level evidence, used as one input, not the answer.)
- Synthesis: rank papers by number of distinct citing papers (R1); ties broken by reuse (R2); report
  R3 alongside. Answer: top 5 with their counts.
- Limits: the corpus is mostly ACL/EMNLP 2025, so papers rarely cite each other; outside citations are
  not in the corpus. A sparse result is a valid finding, stated as such.

For q01-q06 (collection questions: "which benchmarks", "which metrics") the plan usually has one
requirement and a list synthesis; the evidence is the answer. For q07-q12 (best approach, most
influential, leading researchers, most popular benchmark, most successful model, RAG vs fine-tuning)
the plan has several requirements and a real synthesis. The 12 questions stay; the two groups become
"collection" and "synthesis" questions.

## 4. System flow (one agent)

```
question ─► plan propose (model) ─► user picks one ─────► plan.json (frozen, hashed)
                                                         │
                     ┌───────────────────────────────────┴────────────────────────┐
                     ▼                                                             ▼
        gold: every paper, every chunk                              agent run (one agent, sandbox)
        screen ─► extract per requirement ─► rows ─►               search ─► read ─► claim (quote checked)
        triage ─► pool ─► Argilla review ─► evidence key            per requirement ─► synthesise answer
                     │                                                             │
                     └──────────────────────► scoring ◄────────────────────────────┘
                                   evidence recall, support share, synthesis check
                                                     │
                                       provenance graph, web app, report
```

The answer gets two parts: **evidence** (facts, each citing claims, tagged with its requirement id)
and **conclusions** (each with `derived_from`: the evidence fact ids, and the synthesis step used).
The PROV export adds `prov:wasDerivedFrom` from conclusions to evidence facts, so a conclusion can be
walked back to the quotes, as facts can now.

## 5. Gold and scoring

- **Gold evidence key per question**: the gold build (screen → extract → rows → triage → pool →
  review) already works per answer shape; it extracts **per requirement** instead, with the
  requirement's fields and include/exclude criteria. The key holds evidence, not the conclusion, so it
  does not depend on whether the synthesis is right.
- **Reference conclusion**: where the synthesis is computable (counts, ranks), it is computed from the
  gold evidence by the plan's rule, so the gold conclusion follows mechanically from reviewed evidence.
- **Measures**:

| Measure | What it answers | Status |
|---|---|---|
| Support share | are the extracted facts backed by their quotes? (reliability) | built (now primary) |
| Evidence recall, vital recall, per requirement | did it find the evidence? (comprehensiveness) | built as fact/row recall; per-requirement split new |
| Judged precision | of what it extracted, how much did reviewers mark wrong? | built |
| Synthesis consistency | does each conclusion follow from its own cited evidence by the plan's rule? | new (computed where the rule is computable, judged otherwise) |
| Conclusion agreement | does the agent's conclusion match the reference conclusion? | new, secondary |
| Cost | steps, tokens, time | built |

- **Statistics**: RQ1 is an estimate, not a comparison, so there is no hypothesis test. The two primary
  outcomes, support share and evidence recall, are each reported as the mean over the 12 questions
  (each question the mean of its 3 repeats) with a BCa bootstrap 95 % interval; also per question
  group (collection q01-q06, synthesis q07-q12) and per requirement. The run-to-run spread of the 3
  repeats is reported as the system's stability. Pre-registered (outcomes, aggregation, interval
  method, what is left out and why) before any scored run, after the next Slurm test.

## 6. Runs

| Design | Runs |
|---|---|
| RQ1: 12 questions × 3 repeats, one agent, claim on | 36 |
| plan reproducibility (RQ2, optional): 12 questions × 3 proposals | 36 plan proposals, no runs |

One budget for all runs (provisional 60 steps / 2,000,000 tokens, prompt v3), frozen after the Slurm
test.

## 7. What stays and what changes

Stays as built: the sandboxed loop, the claim broker and anchor check, hash-chained events, verify,
the provenance graph and SPARQL store, the corpus, the gold method and Argilla review, the judge and
its calibration, the scoring core, the web app shell and chat.

| Work package | Change |
|---|---|
| P0 remove claim_off | delete the claim_off condition and the attach step (`agent attach`, attach prompts, claim_off prompt and manifests, attach columns in scoring, report and web app); `claim` is always on |
| P1 plan | `plan.schema.json` (section 3), propose prompt, validation, `agent plan propose/pick`; concept sessions migrate to plans |
| P2 agent prompt v3 | follow the plan: work requirement by requirement, keep a coverage note per requirement, then synthesise |
| P3 answer + provenance | evidence facts tagged with requirement ids, conclusions with `derived_from`; verify and PROV export (`prov:wasDerivedFrom`) |
| P4 gold | extraction and rows per requirement; reference conclusion from the reviewed evidence |
| P5 scoring | per-requirement recall, synthesis consistency, conclusion agreement; the report drops the paired claim_on/off test and reports the two primary estimates with BCa intervals |
| P6 web app | plan cards (requirements, criteria, synthesis) with a pick button, no editing; requirement coverage on the run page, conclusion → evidence → quote walk; no condition comparison of claim_on/off |
| P7 subagents | stay off (`--spawn off` is the default, the manifest says off). Optionally delete `agent/spawn.py` and its hooks later to simplify |
| P8 docs | `STATE.md` framing, milestones, pre-registration |

## 8. Order of work

1. **Now**: run the Slurm e2e test (it tests the real-model pieces the new plan keeps: conclude
   replies, claims, gold build, judge, web app), already cut to claim_on runs, no attach, no spawn.
   Do not freeze the budget or pre-register yet.
2. Agree this plan with the supervisor.
3. Build P0-P6 (and P8), with reviewers, as the e2e build was done.
4. Second Slurm test: plans for all 12 questions, gold trial per requirement, a few runs.
5. Freeze plans, budget and pre-registration; gold review in Argilla; the 36 runs; scoring.

## 9. Decisions

Decided (14 Oct, user):

- **D2** the old RQ1 (claim while researching vs attach afterwards) is dropped completely: no
  claim_off condition, no attach step, removed from code (P0).
- **D5** the user only picks a plan; no editing.
- **D7** the 12 questions stay as they are.
- **D1** RQ1 = extraction quality, as the supervisor wrote it ("how reliably and comprehensively
  relevant evidence can be extracted from a scientific corpus").
- **D4** support share (reliably) and evidence recall (comprehensively) are the two primary outcomes,
  each estimated with a BCa interval (no test, since there is no comparison; so no Holm correction).
- **D3** no comparison with an answer-level agent: RQ1 only, 36 runs; stated assessments are one kind
  of evidence inside a plan.
- **D6** every plan's synthesis rule must be computable: the propose prompt requires it (for q07 e.g.
  "best = highest reported score on the most-used benchmark"), and scoring checks conclusions by
  computing the rule. Where a proposed plan still has no computable rule, its conclusions are not
  scored, only its evidence.

Open: whether to keep the optional RQ2 (plan reproducibility; no extra runs, 36 plan proposals).
