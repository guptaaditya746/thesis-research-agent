# Multi-domain question benchmark: design

Date: 16 Nov 2026. Agreed with Aditya in a design interview on the same day. "Aditya's call" marks a decision he
made; "builder's call" marks a default set by the author that Aditya may still overrule.

## 1. Why

The synth2 corpora (`data/synth2/written-full/`, 450 folders) all answer one question: does RAG improve factual
accuracy. Aditya wants the system tested as a general tool: people ask many kinds of questions in many fields,
and the system should handle any question it can answer from the papers. The benchmark must therefore cover
many questions, in several domains, and be easy to grow.

## 2. Goals

- **100 questions:** 4 domains with 25 each. More domains and questions can be added later without rebuilding.
- **Questions of any shape:** not only "does X help?". Aditya's call: flexibility over a fixed form.
- **A known right answer for every question in every folder,** so scores are trustworthy.
- **A system that can answer the new questions,** with each run shown step by step in a simple one-page UI.
- **A downloadable, readable program per run** that rebuilds the answer without any corpus or AI.

## 3. Non-goals and anti-goals

- **No new LLM.** The judge, the paper writer and the system all use the existing cluster model setup (Aditya's
  call). New models are out of scope for now.
- **No pilot run.** Tim dislikes them (reported by Aditya, 2 Nov 2026). Each domain is built completely before
  the next one, not tried on a few papers first.
- **No claim that "the same question always gives the same answer".** It is false today; see section 9.
- **Anti-goal:** 100 near-copies of one question. Two questions count as different only if they ask something
  different.
- **The rule from backend/README.md still holds:** the hashed files listed there are never edited. New
  behaviour goes in new modules.
- **The built corpora stay local.** They are made from renamed real papers, so they are never committed, pushed
  or published.

## 4. Terms

- **Domain:** a field of study (medicine, law, materials science, RAG).
- **World:** a domain's hidden facts, i.e. what the studies found. It is written down before any paper is
  written.
- **Folder (corpus):** one set of synthetic papers built from one world and one seed. A domain has 5 folders.
  They share the same things (drugs, measures, groups) but hide different truths, so one question has
  different right answers across them.
- **Synthetic paper:** a real open-access paper from the field, renamed throughout, with the planted results
  inserted. This is the v11/template-v2 "real edit" method that already passed the realism checks.
- **Answer sheet:** the right answer to one question in one folder, worked out from that folder's world.

## 5. Test material (job 1)

1. **Domains and order:** medicine → law → materials science → RAG. All four get built (Aditya's call).
2. **The world per domain:** the AI drafts it and Aditya edits and approves it before any paper is made. A world
   must be rich enough to carry about 25 questions: several methods or treatments, several measures, studies
   that disagree and the reason why, the datasets or settings used, and the conditions that matter.
3. **Folders:** 5 per domain, each with a different seed and a different hidden truth.
4. **Papers per folder:** the target is 40. Builder's call: start with 20 per folder (400 papers in total) and
   grow to 40 once the deadline allows. Aditya agreed but gave no deadline.
5. **Paper source pools:** open-access papers only. That is PubMed Central for medicine; SSRN or similar for
   law; arXiv or open journals for materials science; the existing HF pool for RAG. Every pool is kept local.
6. **Corpus first, questions second (Aditya's call):** building folders is slow, so they are built once. Aditya
   then writes the questions with the folders' worlds in view.
7. **Old RAG folders:** the 450 existing folders stay as a separate stress test (`twin` must flip the answer;
   `spun` and `duplicate` must keep it). They do not count toward the 100. Their cluster run waits until the new
   material exists.

## 6. Questions and right answers

- **Questions:** Aditya writes 25 per domain. A question can have any shape.
- **Sub-questions:** they are extra input that helps the AI draft the protocol. They are not scored (Aditya's
  call).
- **The right answer:** for each question and each folder, the AI drafts the answer from that folder's world.
  Aditya checks and fixes it on the review page.
- **Scale:** 100 questions × 5 folders = 500 scored answers per system, plus 500 for the baseline.

## 7. Marking

- **A judge model marks everything.** There is no code check, even for fixed-form answers (Aditya's call). The
  judge uses the same cluster model setup as the system (Aditya's call). Known risk: the model partly marks its
  own kind of output, so the judge test below matters.
- **Three scores, kept separate (Tim, M2 §8):**
  - **A:** the facts pulled from each paper, against the planted facts.
  - **B:** the combining.
  - **C:** the final answer, against the answer sheet.
- **Judge test:** Aditya hand-marks about 30 answers on the review page. The report shows how often the judge
  agrees with him.
- **Baseline:** every question is also answered by the plain RAG baseline (`evaluate rag-baseline`), and its
  score is reported next to the system's.

## 8. The system (job 2)

- **Any question:** the system still pulls facts per paper as the protocol says. Then a model writes the answer
  from those facts, citing the paper behind each one (Aditya's call, option a). The 4 existing fixed kinds
  (effect, best, consistency, inventory) keep their rules.
- **Protocol planning:** the planning page gets a box for sub-questions. The AI drafts the protocol from the main
  question and the sub-questions, and Aditya edits it. This follows Tim's compiler chain (M2 §2) and the
  reported wish for a human in the planning.
- **A new one-page UI,** added beside the existing pages, which stay. Top to bottom:
  1. Pick a domain and a folder.
  2. Type the question and its sub-questions.
  3. The AI drafts the protocol, and the user edits it.
  4. Run, with every step after the protocol shown as its own row with a count and a click-to-see list:
     - **Find:** which papers have relevant parts.
     - **Pull out:** each fact, highlighted in its paper.
     - **Combine:** the rule and the facts it counted.
     - **Answer:** each claim linked back to its facts.
  5. The answer.

  The next box opens when the one above is done.
- **A separate review page:** for checking the AI-drafted worlds and answer sheets, and for hand-marking the
  ~30 judge-test answers.

## 9. Evidence as a program

- **Every finished run downloads as one file:** a Python program written to be read by people. It uses long
  plain names, one short step per line, and only the Python standard library.
- **What the file holds:** only the facts that were used, written as values. Each fact has a comment with its
  paper, section and exact quote. The file also carries its own copy of the rules (builder's call: no import
  from the repo, so it still runs years later).
- **What it does:** it needs no corpus, no AI and no repo. Run it, and it prints the same answer every time.
- **Model-written answers:** when a model wrote the final text, the file holds it as pasted text marked "written
  by a model from the results above, not rebuilt by this file" (builder's call).
- **The thesis claim (Aditya's call):** "replayable and checkable". The same recorded facts always rebuild the
  same answer, and every fact points to exact text in a paper.
  - It must not claim that the same question always gives the same answer, that extraction is deterministic, or
    that tool use is deterministic.
  - The accurate wording is: the tools are fixed functions; the agent's choice of tool calls is not fixed, but
    every call is recorded.
- **Measurement:** one folder is re-run 5 times with no cache (`evidence reexec`). The report gives:
  - the share of identical model calls;
  - item stability, and whether the final answer stays the same;
  - the agentic extractor (temperature 0.7) and the LLM extractors (temperature 0) separately.

  Background, from a code read on 16 Nov 2026 with nothing run: replay already checks every output hash. The
  run folders are already sealed with a manifest. No re-execution has been measured yet.

## 10. Left to the builder

- The file formats for worlds, questions and answer sheets.
- How a world is turned into planted facts per paper (extend synth2 or add a new module; not the frozen `synth`).
- The judge prompt, following docs/prompt-writing.md.
- The layout details of the two pages.
- How the readable program is generated from a run folder.

## 10b. Settled after the builder check

- **"Can't tell" is a valid right answer** when a folder does not plant the facts a question needs. The answer
  sheet says so, and the system must be able to say it. Builder's call; this fits Tim's view, reported by
  Aditya on 2 Nov 2026, that an empty answer is okay.
- **Score B for model-written answers:** the judge checks whether the answer used the pulled facts correctly
  (nothing invented, nothing contradicted). Builder's call.
- **Realism per domain:** the realism checks used for RAG (blind reader, real-vs-synthetic classifier) run on
  each new domain's finished folders. This is a check after the build, not a pilot. Builder's call.
- **Mix of question kinds:** there is no quota. Aditya writes questions freely. The readable program rebuilds
  rule-based answers fully and carries model-written text as recorded text. Builder's call.
- **Judge agreement:** the report gives the agreement with Aditya's hand marks, and any rate below 80% is
  flagged as a limitation. Builder's call.
- **Law source:** SSRN papers are free to read. They are used, and kept local like every pool. Builder's call.
- **The answer sheet is a checklist (Aditya's call):** it lists the key points a right answer must make. The
  judge ticks each point, so 2 of 3 points earns partial marks and the report shows which points were missed. A
  "can't tell" sheet has a single point: the answer says the folder cannot answer the question.
- **Review load (Aditya's call):** Aditya checks every answer sheet for one folder per domain (100 sheets in
  total). The AI drafts the other 4 folders the same way, and Aditya spot-checks 20 of them.

## 10c. Settled after the plan review (16 Nov 2026, Aditya said yes to all five)

- **Measured values, not only counts:** a measure is either a count ("45 of 100 patients improved") or a measured
  value ("mean strength 410 MPa, SD 22, n 30"). Both kinds are in from the start.
- **More hidden facts:** these carry truth:
  - a condition can come from the setting itself (e.g. university hospital or community clinic);
  - each domain has at least 3 measures;
  - some studies compare two treatments head to head, with no control.
- **Exaggerating authors:** some papers claim more than their numbers show (Tim, 14 Oct: "A particularly
  interesting test would be to generate papers in which the authors' conclusions are overly optimistic…"). Which
  claims exaggerate is recorded in the truth.
- **"Can't tell" happens on purpose:** some folders leave one treatment–measure pair with no studies.
- **Approve the drawn facts before building:** Aditya sees the hidden facts drawn for all 5 folders, may edit
  them, and approves them before any paper is written.
- **40 studies per folder (builder's call):** the richer world needs them, so the "start with 20" default of §5.4
  is dropped for synth3. This is the spec's original target.

## 11. Open, needing Aditya

- **The thesis deadline.** It decides 20 or 40 papers per folder (builder's call: start with 20).
