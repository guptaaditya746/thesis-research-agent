# synth3 real papers (plan 2 of 5): handoff

Finished 18 Nov 2026 on branch `synth3-real` (from main @ 2a9301d9 to c4392eab). Not pushed or merged.

## State
- 12 tasks done, each reviewed; a final whole-branch review (0 critical, 4 important, 8 minor) and one fix pass; re-check found all fixed.
- Tests: synth3 175 passed; whole suite 3377 passed, 36 skipped.
- Medicine: pool of 286 open-access PubMed Central papers (30 kept aside for the realism test), 5 real folders in data/synth3/built/medicine-real (local only). Each folder's answer key equals the practice folder's for the same seed.
- Law, materials science, RAG: draft specs in data/synth3/drafts/ and real-paper configs; nothing drawn, approved or built.

## Judgement calls I made (from the ledger, with their cost if wrong)
- Setup: Ruling: plan reviewed before execution by a fresh Opus reviewer (.superpowers/sdd/plan2-review.md: 0C/6I/18M), planner fixed all Important and all Minor but M18 — cost if wrong: conflicts surface in task review.
- Setup: Ruling: never stage backend/agent/tests/test_prompts.py (unrelated uncommitted change) — cost if wrong: unrelated change in a commit.
- Task 1: Ruling: heading() needs a leading '#' — later tasks feed markdown '##' lines only (plan grep) — cost if wrong: a bare-text heading is missed.
- Task 5: Ruling: two plan-mandated Important findings fixed against the brief's wording (replacement surname may be a real cited author; lower-case keep placeholder makes synth2 rename the next capitalised word) — both break "real names are renamed" — cost if wrong: a few lines.
- Task 5: Ruling: name_words of <= 3 letters (Minor) folded into the fix round (same file) — cost if wrong: one check.
- Task 7: Ruling: plan-mandated "captions left + 1" table number replaced by "one above the highest real table number", and sentences citing a dropped table are cut — duplicate/dangling table numbers mislead readers and the realism check — cost if wrong: a few lines.
- Task 7: Ruling: clean_title add-on garble and Results-and-Discussion heading Minors folded into fix round 1 (same file) — cost if wrong: two small tests.
- Task 7: Ruling: renamer turned capitalised heading words ("Discussion" in "## Results and Discussion") into names — Task 5 defect found in Task 7; fixed in this fix round by building the name map without heading lines — cost if wrong: a heading-only real name stays (body names still renamed).
- Task 7: Ruling: re-review's open point (a plain-word place name that appears ONLY in the title/a heading is not renamed and names_left cannot flag it) accepted, not fixed — keeping title words in the map would rename title-case words ("Older", "Adults") everywhere; Aditya already accepted that real-edit papers are recognisable to someone who knows them; it is a recognisability cue, not a truth error — cost if wrong: a rare real place name in a title.
- Task 9: Ruling: scoped re-review done by the controller reading the 12-line code diff (rmtree at start, work under pools/<domain>/realism-work, empty groups skipped) instead of a dispatch — cost if wrong: a missed detail in a tiny diff.
- Task 11: Ruling: reading found off-topic (non-drug) sources, "usual care" left beside planted "Standard care", broken words ("GHZatio", "lowto"), "the Cardivel" wording (clearest synthetic cue), and a cp1252 crash in pool-fetch's licence print — all fixed in one fix wave with root causes and tests, then rebuild; the "the <arm>" fix changes template papers on purpose (pin updated) — cost if wrong: one rebuild.
- Task 11: Ruling: no separate re-review of the fix wave; the final whole-branch review is pointed at it explicitly — cost if wrong: findings arrive one step later.
- Task 12: Ruling: Task 12 (data drafts + one parametrized test) is reviewed inside the final whole-branch review instead of a separate task review — cost if wrong: findings one step later.
- Final: Ruling: real drug names outside the list surviving (axitinib, sildenafil, rilmenidine, prazosin) re-graded Minor → Important — Global Constraints say real names are renamed — cost if wrong: a few stems.

## Small issues left for later (deferred minors)
- Task 1: minor (deferred): banned() would get an empty alternative if a spec had no arms and no settings.
- Task 1: minor (deferred): one error message names max_fetch for both max_fetch and min_tables.
- Task 1: minor (deferred): medicine config test checks few fields (keep/name lists, heading with real regexes).
- Task 1: minor (deferred): RED run failed on conftest import, not the missing module (process).
- Task 1: minor (deferred): evidence/tests/test_parallel.py::test_workers_keep_several_calls_in_flight flaky under full-suite load (passes alone).
- Task 2: minor (deferred): tidy's _EMPTY_BRACKETS/_URL also run on table blocks (a cell like "12 (–)" can lose brackets).
- Task 2: minor (deferred): table/Docling tests are thin (no exact table string, no assert that Acknowledgements subsections, www. URLs, heading numbers go).
- Task 2: minor (deferred): _CAPTION fails on captions with '*'; "Table 1: x" becomes "Table 1. : x".
- Task 2: minor (deferred): a Docling heading with body text directly under it (no blank line) is not recognised.
- Task 2: minor (deferred): raw jats_paper text keeps " ," / " ." where citations were removed (tidy fixes prose).
- Task 3: minor (deferred): negative or huge Retry-After not clamped (negative crashes time.sleep).
- Task 3: minor (deferred): no tests for "still 429 then raise", 503, or the licence value on a PMC row (jats_paper does fill it, pmc.py:101-109).
- Task 3: minor (deferred): import order in pool.py; a.md and a.xml share id "a" silently; fetch_pool imports pool inside the function (circular); corrupt index.json gives a traceback.
- Task 4: minor (deferred): same-split test compares only `test` (not sources/seed/sha, not reversed index order).
- Task 4: minor (deferred): write_pieces notes dropped; stale pieces/ files may survive a failed retry.
- Task 4: minor (deferred): import grouping in pool.py; pool-split CLI has no test.
- Task 5: minor (deferred): \b treats digits/_ as word chars ("amlodipine10" not caught); CamelCase planted word inside a value passes; no tests for sayable redraw / 3-letter stem prefix.
- Task 6: minor (deferred): intro "{label} is {description}." assumes noun-phrase descriptions (medicine's are).
- Task 6: minor (deferred): realwrite.CLOSERS shares a name with write.CLOSERS; digits test runs prose level only; import grouping in test_corpus.py.
- Task 7: minor (deferred): real between-arm sentences that never name the control survive ("similar in both groups") — synth2 v11 rule set; note for realism/blind reader.
- Task 7: minor (deferred): seed-independent failures (uncleanable title, duplicate banned block) are retried MAX_SEEDS times.
- Task 7: minor (deferred): per-source retry bound lives in the build loop (Task 8 must cap rejected sources).
- Task 8: minor (deferred): a missing pool full/ file raises OSError (CLI catches only ValueError → traceback).
- Task 8: minor (deferred): realcorpus imports private realwrite._words; --out outside data/synth3/built/ would put real/maps where git could see them.
- Task 8: minor (deferred): rejected-source replacement tested only via a wrapped edit_study (fake pool never rejects).
- Task 9: minor (deferred): arm labels with non-word edges ("Drug (A)") miss \b; no test that masked copies on disk are masked on both sides, nor of style_gap args / CLI path.
- Task 10: minor (deferred): a wrong-valued row gives two problems ("not planted" + "missing or other values"); round(mean, None) unchecked; claim with another measure name ignored; prompt examples are fragments, no no_effect example; read_folder aborts on one failed call (cache resumes).
- Task 10: minor (deferred): no clean RED run (tests and code written together).
- Task 11: minor (deferred): a few kept papers with 10-12 drug names are not trials; synth2 renames Title Case phrases ("Good Clinical Kihomajaik"); "Overall," opening every claim is the top synthetic cue; s4/s5 style gap inflated by quote marks absent from the real test pieces.
- Task 12: minor (deferred): real configs for law/materials/rag untested on real papers (query, keep lists, name_words, min_names are guesses until a first fetch).
- Final: minor (deferred): exclude_title uses ASCII '-' only, so "meta‐analysis" with U+2010 slips past the off-topic filter.
- Final: minor (deferred): rag draft control description is a clause (reads badly in "{label} is {description}.").
- Final: minor (deferred): common-noun labels read oddly without "the" ("compared with Standard care").
- Final: minor (deferred): _plural_acronyms misses a singular that only occurs inside a renamed multi-word key.
- Final: minor (deferred): synth2's map renames "Declaration of Helsinki" (90 papers) and "Fig" (48) — strong realism cues.
- Final: minor (deferred): pmc.py imports private helpers from evidence.sources.pmc.
- Final: minor (deferred, FOR ADITYA): the medicine author list (approved, committed) includes "Nadia Rosenthal", a well-known real scientist; the drafts copy the list. Changing medicine.yaml changes its hash, so the 5 approved worlds would need re-drawing/approval — Aditya's call.
- Final: minor (deferred): rag min_names 1 may reject papers naming only DPR/BM25; ALL-CAPS lines in "Study Highlights" boxes still renamed.
- Final: re-review ADDRESSED all 5 (I1-I4 + drug names); no new Critical/Important. Final: minor (deferred): calm_caps lowercases an acronym seen in capitals only inside a heading ("## NYHA CLASS" → "## Nyha Class").
