# synth3 questions, answer sheets and judge (plan 3 of 5): handoff

Finished 18 Nov 2026 on branch `synth3-questions` (from synth3-real @ c4392eab to af1f43b1). Not pushed or merged.

## State
- 13 tasks done, each reviewed; a final whole-branch review (1 critical, 4 important, 8 minor), one fix pass, and a
  re-check that found all fixed. One residual (agreement numbers moving with each hand mark) fixed after it.
- Tests: synth3 + webapp 611 passed, 19 skipped; whole backend suite 3576 passed, 36 skipped (3 load-flaky tests pass
  alone); frontend 171 tests (one known load timeout in flow.test.tsx passes alone), typecheck and lint clean.
- New commands: `synth3 questions`, `draft-sheets`, `collect`, `baseline`, `judge`, `judge-sample`, `report`; the
  review page at `/review` (worlds, answer sheets, judge test) over the API at `/api/ev/review`.
- No question file, sheet, answer, mark or hand mark exists yet. Nothing ran on the cluster.

## What it does, in one breath
Aditya writes questions; the drafter (orch-model) drafts an answer sheet of points per question and folder; he
checks the sheets on the page; the baseline and (plan 4) the system answer; `judge` (sub-model-1) gives each answer
three separate scores: A (planted facts found among the pulled facts), B (claims supported by the facts used),
C (sheet points met). `judge-sample` picks ~30 answers he marks by hand, blind; `report` shows A, B, C per system
next to the baseline and the judge's agreement with him (below 80% is reported as a limitation).

## Judgement calls I made (from the ledger, with their cost if wrong)
- Sub-questions set no scope and are never scored or sent to drafter, judge or baseline; sheets are keyed to
  {question, about} only, so editing a sub-question never stales a checked sheet — cost: one line if they should set scope.
- A failed model call marks the item pending, the run goes on; a pending item is asked again past the cache next run — cost: extra calls on pending items only.
- draft-sheets never overwrites a checked or person-written sheet; a stale one is archived (`.stale-n`), never deleted — cost: none.
- All three judges get each measure's direction (higher/lower better) from the spec — cost: one input block.
- Judge A: a pulled fact that correctly states a different planted fact makes this one "missing", not "wrong"; code rejects a reply that does otherwise — cost: a few extra pending items.
- The judge runs on unchecked (drafted) sheets too; each mark records the sheet status and the report counts them — cost: none.
- Hand marking is blind: no system name, no fact kind, a seeded shuffled order, no judge result on the page, and the report holds back every agreement number until all ~30 are marked — cost: one field.
- Only current marks count: a marks file whose answer, sheet or question changed is set aside or counted as "not current"; a hand mark keeps the hashes it was made on and is asked again when they change — cost: none.
- The baseline re-runs when its folder changes (corpus id) — cost: none.
- The drafter prompt sheet-v1 was edited in place (never run, no sheets exist); any change after the first real draft is a sheet-v2.

## Small issues left for later
- Duplicate claims can skew B (needs a definition of "duplicate"); do with plan 4's first run.
- Judge prompt wording (A/B/C minors) waits for the 30-answer judge test, as the reviewers asked.
- A page edit can be lost to a second open tab or a parallel draft-sheets (never a checked or person-written sheet).
- Duplicate keys in a hand-written YAML file are not caught.
- Re-run `collect`, `baseline` and `judge` together after editing questions: re-running only some can show which
  items are the baseline on the judge-test page ("mark again" vs "not judged yet").
- A sub-question edit asks him to re-mark baseline items whose text did not change (the answer hash covers the whole record).

## Notes
- Known limitation: judges can tell the baseline by the look of its input (passages with empty fields, `[S003, ...]`
  citation marks), though no system name reaches them. Report it beside spec §7's "marks its own kind of output".
- Plan 4: `question_sha256` leaves out `kind`; if the system reads `kind`, answer records must hash it. Fixed-kind
  answers dumped whole can hit the 12,000-character cut.
- New synth3 modules change `synth3.corpus.code_sha256()`, so folders built after this plan record a new generator
  hash; nothing checks it.

## For Aditya, in order
1. Write 25 questions per domain in `data/synth3/questions/<domain>.yaml` (format: `backend/synth3/questions.py`
   docstring); check with `uv run synth3 questions --domain medicine`.
2. Cluster: `uv run synth3 draft-sheets --domain medicine`; on `/review` check every sheet of s1 and the 20 marked "sample".
3. Cluster: `uv run synth3 baseline --domain medicine`.
4. After plan 4's runs: `uv run synth3 collect ...` per run, then `uv run synth3 judge --domain medicine`.
5. `uv run synth3 judge-sample --domains medicine`, hand-mark the 30 on `/review`, then
   `uv run synth3 report --domains medicine --out data/synth3/results/report-medicine.json`.
Repeat 1-4 for law, materials and RAG once approved; for 5 use `judge-sample --add N`. Click through `/review` once
(it was never clicked in a browser). Decide: should sub-questions help the drafter read the question?
