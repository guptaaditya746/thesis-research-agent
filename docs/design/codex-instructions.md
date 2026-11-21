# Codex: standing instructions (work independently)

Written 21 Nov 2026 for Codex on the GPU compute node. Work through the queue below in order without waiting for
Aditya, unless a STOP rule fires. Keep a running log in docs/design/codex-log.md (date, task, what changed, test
results, numbers). Aditya reviews that log; keep each entry short and plain.

## 0. Read first, every session

AGENTS.md, CLAUDE.md, docs/prompt-writing.md (mandatory for any prompt), docs/design/slice1.md,
docs/design/population.md (plan v2: domain-free settings), docs/design/audit-inflation.md (your audit),
docs/design/codex-prompt-population.md (Part B-D details), docs/design/qwen-writer.md.

## 1. Hard rules (never break)

1. Do not commit, push, or rewrite git history. Never touch llm-setup/ (read-only).
2. Never print or log LITELLM_MASTER_KEY or S2_API_KEY (.env). No personal data in web requests.
3. Domain-free: no domain word lists, regexes, field names or thresholds in backend/evqa pipeline (spec/, find/,
   extract/, answer/) or scorer (eval/). The LLM decides meaning; code checks grounding (quotes, offsets, numbers)
   and structure. Domain knowledge only as optional plug-ins the pipeline runs without.
4. No BM25 and no embedding model (Aditya's decision). Find = exact-word search + LLM search terms + agent.
5. Tune only on the PRACTICE split (data/dataset/medical/questions/practice.jsonl, 22 questions). Never open
   per-question outputs of test runs (bench-*) or hold-out runs (holdout-*) to fix code or prompts. Read only their
   eval.json "totals" for reporting.
6. At most 3 LLM calls at once across ALL processes. Before starting anything that calls Qwen or Claude, check
   `pgrep -af "evqa run|paper_writing_cli|evqa paper"`; if another LLM job runs, wait (poll every 5 min) or do a
   no-LLM task meanwhile. Task Q0 below makes this automatic.
7. Every LLM output is checked by code; generation and verification are separate calls.
8. Run Qwen work as `srun --jobid 9808 --overlap ops/injob.sh uv run ...` from the repo root (or directly with
   ops/injob.sh when you are on gammaweb08). Qwen: configs with `think: false`.

## 2. Do not edit (someone else is working there)

- external/paperorchestra/, backend/evqa/research/, backend/evqa/paperwriter.py, the `paper` part of
  backend/evqa/cli.py, data/style/, runs/scratch/qwen_quality/ (a Claude agent builds the Semantic Scholar tool).
- data/seed/medical_holdout/, data/dataset/medical_holdout/, configs/evqa/holdout-*.yaml (frozen hold-out).
- data/dataset/medical/ papers and questions, data/seed/medical/ gold (frozen benchmark).
- Files a running `evqa run` reads: while `pgrep -af "evqa run"` shows a run, do not change backend/evqa/{spec,
  find,extract,answer,eval,seed,lm,contracts,corpus,run}.py or their packages. Work in a git worktree meanwhile
  (`git worktree add ../tra-codex HEAD`, no commits; bring changes back as a patch: `git diff > x.patch`, apply on
  main after the run ends, then `git worktree remove`).

## 3. STOP rules (write in codex-log.md, then wait for Aditya)

- A change would need editing a "do not edit" path or llm-setup/.
- A practice score drops by more than 0.05 on any layer and you cannot explain it in two tries.
- A frozen file (questions, gold, seed.ttl of medical or medical_holdout) would change.
- Anything needs money beyond the cheapest Claude model for verification, or more than 3 parallel LLM calls.

## 4. The queue (do in order; each item: tests + log entry)

Q0. Cross-process LLM cap (no LLM). evqa/lm.py uses an in-process semaphore; the writer uses flock slot files in
    data/cache/claude-slots. Make evqa's Qwen and Claude calls take the same kind of flock slots (one shared folder
    per backend, cap 3), so two processes can never exceed 3. Test with two processes and a fake slow call.

Q1. Install plan v2 steps 1-2b (your isolated draft) once no `evqa run` is active. Checkpoint on practice: run
    Spec + Find + Extract on the 22 practice questions; write docs/design/checkpoint-settings.md with, per question,
    the dimensions Spec proposed, and per paper the settings Extract read (value + quote), extra settings found,
    and check failures. Acceptance (continue without waiting if all hold): >= 90% of extracted settings pass the
    quote check; no setting value copied from the question that the paper does not support; the fasting/fed test
    passes. Otherwise STOP.

    Q1 fix (Aditya, 21 Nov): extract/settings_v2.py `check` tests quotes with plain `quote in text`, so a quote
    that differs only by a line break, dash type or curly quote fails. Use extract/anchor.py `find`/`spans` (same
    normalisation as row quotes, gives offsets for the provenance scorer) for both dimension and extra-setting
    quotes; keep "value in quote" and "numbers in quote" checks. Add a test with a line-break and an en-dash quote.
    Report how many failed checks this recovers on practice.

Q2. Plan v2 steps 3-7 (links generator + verifier, Answer, provenance scorer, deletions, second-domain fixture).
    Practice run before/after with the same config; record calls and tokens per question.

Q2b. Zero hard-coded text + libraries (Aditya, 21 Nov: top priority after Q2 code; no Qwen needed for most).
    First a guard test (backend/evqa/tests/test_no_word_lists.py): scan spec/, find/, extract/, answer/, eval/,
    norm.py, lm.py with `ast`; fail on any set/tuple/list/dict literal holding >= 3 natural-language word strings
    (allow-list only JSON/schema keys and contract field names, each allow-listed with a one-line reason). It must
    fail today; then remove until it passes:
    - answer/canon.py SLOTS, TIME_UNITS, TO_WEEKS -> Pint (units and conversions from its registry); slot names ->
      Spec dimensions. FILLER, SPELL -> delete; sameness is decided by the Q2 link step (LLM + verifier), with
      RapidFuzz `token_set_ratio` only as a candidate score (threshold in configs/evqa/linkage.yaml, practice-tuned).
    - norm.py DOWN, AFTER (direction words) -> Extract returns the value's sign/direction with its quote; code checks
      the sign against the number. No English word list.
    - answer/core.py OWN, CONFLICT_SLOTS, CONFLICT_LABEL, answer/papers.py DESIGN -> from Spec dimensions.
    - population.py (v1 medical) -> move to backend/evqa/plugins/medical/ (off by default) or delete.
    - Passages/quotes: markdown-it-py for sections and tables with exact offsets; pysbd for sentence spans.
    - lm.py: vLLM structured output (`response_format: json_schema`) for Qwen calls; keep code checks + retries.
    Splink: once settings are extracted (rows x dimensions = a table), add it as a link-candidate scorer in front of
    the LLM link verifier, and an ablation in Q5 (Splink-only vs LLM-only vs Splink+LLM) on practice; report link
    precision/recall vs gold provenance and LLM calls saved. dedupe only if Splink fails.
    Practice before/after when Qwen is back; until then fake-LM tests and log "practice pending".

Q3. Remove the remaining "tuned" rows of audit-inflation.md (non-seed, multi-domain prompt examples; drop the
    ellipsis-quote relaxation or replace it with anchored spans; `named_in_paper` -> subject-to-value evidence).
    One prompt version bump per changed prompt, old text kept. Practice before/after.

Q4. Domain-free data generation (in the worktree while a run is active): seed build + bench driven by the blueprint
    (it declares items, dimensions, measures, effect model and question templates). Medical must rebuild
    byte-identical (seed.ttl, questions, gold: compare sha256). Then build data/seed/materials (your draft
    blueprint) with code only. Writing materials papers waits for the Qwen writer (qwen-writer.md) and Aditya's go.

Q5. Experiment harness (things we use while improving the system):
    - configs/evqa/ablations/: practice configs that switch one part off each: search_terms, gap agent, extra
      settings, link verifier (use verifier = accept generator), closed book.
    - `evqa compare <run_dir>...`: one Markdown table of totals per layer + per type + calls/tokens/seconds per
      question, and the per-question differences (practice only). Write it to runs/evqa/compare-<date>.md.
    - Run all ablations on practice once; put the table in codex-log.md.

Q6. Robustness checks (practice only), as an `evqa probe` command, each a pass/fail report:
    - paraphrase: 2 rewordings per practice question (Claude cheapest model, blind verifier that the meaning is
      kept, as in seed/reword.py); the answer must not change.
    - rename: made-up drug names replaced by new made-up names in papers + questions (code only); answers must
      change only in the names.
    - order: papers listed in another order; answers must not change.
    - distractor: add 3 off-topic papers (code-made, from other practice briefs with names swapped); answers must
      not change.
    Log failures with the step that changed (spec/find/extract/answer).

Q7. Error-analysis report for practice runs: `evqa explain <run_dir> <qid>` prints, in plain words, why the answer
    is right or wrong per fact (blame layer, the passage, the row, the quote), and the Workbench run pane gets a
    "why" link per question that shows the same (keep vitest passing).

Q8. Regression net: freeze the practice outputs of code-only steps (Answer from given rows; scorer from given run
    folders) as fixtures under backend/evqa/tests/fixtures/; a test fails if code changes their output without the
    fixture being regenerated on purpose (`--regen` flag).

Q9. Final scores (only after Q1-Q3 are done and practice is stable): one bench-qwen (test) run and one
    holdout-qwen run with the new code, read totals only, put both next to the old numbers in codex-log.md with the
    caveat that test was seen during earlier tuning and the hold-out was not.

## 5. How to test (every item)

- `uv run pytest -q backend` (about 6-7 min) must pass; new code gets tests with fake LMs / fake HTTP (no network).
- Workbench, if you touch frontend/: `export PATH=~/.nvm/versions/node/v24.16.0/bin:$PATH; cd frontend &&
  npx tsc --noEmit -p . && npx eslint . && npx vitest run && npx vite build`.
- Practice run: copy configs/evqa/bench-qwen.yaml to configs/evqa/practice-qwen.yaml with `split: practice`;
  `evqa run --config ...` (resumable; scores itself). Compare with `evqa compare` (Q5) once it exists.
- Before claiming a gain: same config except the change, practice only, numbers in the log.

## 6. Log entry format (docs/design/codex-log.md)

```
## <date time> Q<n> <title>
Changed: <files, one line each>
Tests: <pytest result>, <vitest if any>
Practice: <before -> after per layer, calls/question>   (or "no LLM")
Notes: <what is unsure, what Aditya should look at>
```
