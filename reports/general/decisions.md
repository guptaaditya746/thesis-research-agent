# General-system run decisions

## 2026-11-04: Use plain text for DSPy model replies

- Chosen: give DSPy calls a dedicated `PlainTextReply` record type that requests plain text from the model and wraps it only after receipt for existing recording. Other typed calls keep their schema-constrained output. The new type changes the prompt/schema hash so old wrapped-response cache entries are not silently reused.
- Why: the actual ReadClaim prompt returned valid JSON in two plain-chat probes, while the forced outer `{"text": ...}` schema repeatedly produced truncated output. The change covers both direct ReadClaim and recorded stage DSPy calls without changing the task prompt, scoring or gold labels.
- Undo: revert the commit introducing `PlainTextReply` and its use in `evidence/stages.py`; restore the prior `Reply` type and schema-constrained call. Historical stage replay compatibility across this change needs verification because the prompt hash differs.

## 2026-11-04: Leave SOFC-dependent tuning out of this run

- Chosen: proceed with SciLead and SciREX without SOFC tuning or hand-created training examples; the user explicitly asked to skip SOFC tuning.
- Why: compatible SOFC input and real tuning examples are not available yet, and synthetic-only tuning for those steps is refused by the runbook.
- Undo: after converting and verifying SOFC data, prepare its held-out split and examples and follow sections 5.2–5.4 in a separate, explicitly approved tuning run before starting dependent evaluations.

## 2026-11-04: Skip the SciLead hand-confirmed row

- Chosen: continue with the automatic SciLead rows without a hand-confirmed row after the user requested continuation without naming a reviewer.
- Why: section 6.2 requires a named person to read and confirm the first five plans and explicitly allows skipping that row when no name is supplied.
- Undo: have a named reviewer inspect and confirm the first five existing plans, then run and score the hand rows as directed in section 6.

## 2026-11-04: Run SciLead reasoning rows concurrently

- Chosen: start the reasoning-off row alongside the reasoning-on retry, using a separate cache directory for reasoning off.
- Why: the user requested up to four parallel tasks; the rows have separate output directories and a separate cache avoids concurrent writers to the same cache file.
- Undo: stop the reasoning-off process, preserve its outputs and cache, then resume it after the other row completes using the same cache directory.

## 2026-11-04: Make plan-run test fakes return plain text

- Chosen: update plan-run fake model responses to follow the requested text output mode, retaining their structured response behavior for structured calls.
- Why: the production DSPy transport now requests raw text, but these fakes still sent the old outer text object, causing parsing failures unrelated to model behavior.
- Undo: revert the `stage_reply` helper and its use in the three plan-run test files.

## 2026-11-04: Convert SOFC-Exp conservatively

- Chosen: convert source frames and sentence offsets to the runbook JSON, retaining span IDs, repeated slot references, links and raw value strings. Leave value-to-material links null; parse only simple number-and-unit strings.
- Why: the release annotates experiment slots but does not explicitly pair each measurement to a specific material; inferring that relation would fabricate gold labels. Complex numerical expressions must remain identifiable without guessing their normalization.
- Undo: remove `evaluation/realpapers/convert_sofc.py` and its converter test, and set aside the generated SOFC JSON files; the source ZIP remains unchanged.

## 2026-11-04: Preserve MeasEval annotations and expose the scalar-only subset

- Chosen: convert one explicitly selected original split at a time, retain every original annotation and excluded quantity, and populate the existing evaluator's numeric quantities only for a single literal scalar followed by its documented unit. Resolve entity links within the annotation set; ambiguous entities stay null. Keep `layout_verified` unchanged.
- Why: the evaluator accepts only one float, unit and entity, while the real release also contains ranges, lists, written numbers and other expressions. Treating one number in a range as the gold answer would invent labels. The resulting score, if used, covers only the listed scalar subset and must never be represented as full MeasEval performance; no source data or split was changed.
- Undo: remove `evaluation/realpapers/convert_measeval.py` and its test; keep the original ZIP and generated files as provenance. Use the complete original annotations to build an evaluator that supports their full semantics.

## 2026-11-04: Defer CochraneForest

- Chosen: leave CochraneForest out of this run after one public search did not identify a dataset archive.
- Why: its release and expected input cannot be verified from the search results.
- Undo: obtain the release, inspect its contents and provenance, and complete the runbook's layout checkpoint before evaluation.

## 2026-11-04: Preserve extractor fingerprint integrity

- Chosen: retain the changed extractor fingerprints and the unchanged historical protocol-lock fixture while investigating historical replay; do not force a former code digest or replace the expected fixture.
- Why: extractor fingerprints intentionally include `modelcall/call.py`, whose behavior changed. Reusing an older digest without proving equivalence across all calls could cause stale extraction results to be accepted under the same cache key. The old-lock stability test currently fails, so the offline requirement is not yet met.
- Undo: revert this decision after implementing and testing an explicit versioned compatibility mechanism that keeps current and historical identities distinct and validates replay of a run recorded before the change.

## 2026-11-04: Hold SOFC frame scoring for repeated slots

- Chosen: report the mismatch between repeated source slot references and the current evaluator's joined-string matching, and hold interpretation of SOFC frame scores pending review.
- Why: 352 of 1,032 converted frames contain repeated slots, whose members the evaluator currently demands together in one predicted setting. Changing scoring without review would change the benchmark's semantics.
- Undo: after a reviewed evaluator supports repeated source slots, recheck the original frame references and run the SOFC frame evaluation with the revised evaluator.

## 2026-11-04: Merge query parameter fix and expand evaluation

- Chosen: merge `origin/fix/query-params` and run the full kept SciLead and SciREX sets in new output directories, reusing existing plans and caches; generate plans only for questions that do not yet have one.
- Why: the user requested the metric parameter fix and all held-out-safe questions; separate run folders ensure old sealed runs do not suppress the reruns.
- Undo: revert the merge and set aside the new full-set run and score directories; previous plans and runs remain available.

## 2026-11-04: Start existing SciLead plans while remaining plans are prepared

- Chosen: run the first ten existing plans in the new full-set reasoning-on folder while the planner creates only missing plans, then complete the row with all 22 after both steps finish.
- Why: the user authorized parallel work, and the runner skips sealed completed questions when the full row resumes; no two run processes write the same row at once.
- Undo: stop the initial run process, preserve any partial folders, and resume the full 22-question row after planning finishes.

## 2026-11-04: Process newly ready SciLead plans in batches

- Chosen: snapshot the IDs whose plan files already exist and run each reasoning row against that snapshot, then resume the full 22 after planning completes. Use each row's existing cache.
- Why: this keeps evaluation moving while remaining plans are prepared; completed question folders are skipped on continuation, and only one process writes each row.
- Undo: stop the batch processes, preserve partial outputs, and resume the full sample once planning has finished.

## 2026-11-04: Resume interrupted SciLead rows

- Chosen: resume each full SciLead row from its saved folders using the existing row cache, under monitored launchers; the detached attempt did not persist.
- Why: the original launcher processes disappeared before recording completion; the runner skips sealed runs and preserves unsealed runs before retrying.
- Undo: stop the launcher steps and retain the existing run and failed-sibling folders for inspection.

## 2026-11-04: Prepare the SciLead RAG baseline during retries

- Chosen: run the RAG-only baseline for the same 22-question selection in a separate score directory, reusing the runbook RAG cache; produce the final combined score after the engine retries finish.
- Why: the user requested parallel work, and the baseline does not read or overwrite the active engine run folders.
- Undo: retain or set aside the RAG-only output and run the combined scoring command after retries as usual; the source questions and labels remain unchanged.

## 2026-11-04: Record storage and service recommendations without migrating

- Chosen: document the independent artifact, pipeline, and service review; continue the authorized Git copy for this run.
- Why: no durable object-store endpoint or access has been verified, and architecture changes need stable replay and cache contracts before deployment.
- Undo: update or remove the recommendation document after selecting and verifying an alternative storage or architecture design; retain existing run artifacts.

## 2026-11-04: Expand SciREX without replacing existing plans

- Chosen: use the 15 kept questions and existing SciREX plans and cache; generate only the five missing plans. Proceed with automatic rows without a hand row unless a reviewer is named.
- Why: the user requested all 15 questions with existing plans preserved; the runbook allows skipping the hand row when no reviewer name is supplied.
- Undo: set aside the full-set outputs and use the original ten-question selection and saved plans; the old selection is unchanged.

## 2026-11-04: Run initial SciREX reasoning rows in parallel

- Chosen: use copies of the ten existing plan files in a separate reasoning-off plan folder and a separate off-row cache while the on row and remaining plan generation run.
- Why: this avoids simultaneous writers to confirmation files and JSONL caches while using the same plan content; previously existing planner cache remains in use for new plans.
- Undo: stop the off row, retain its cache and outputs, and rerun it sequentially with the original plan folder after the on row finishes.

## 2026-11-04: Prepare SciREX baseline alongside engine rows

- Chosen: run the RAG-only baseline for the same 15-question selection in a separate score directory and its existing baseline cache; combine scores after engine rows and retries finish.
- Why: the user requested parallel work; this process does not write the engine row folders and uses the same held-out-safe sample.
- Undo: retain or set aside the RAG-only output and run the normal combined scoring command after the engine rows complete.

## 2026-11-04: Record independent improvement review

- Chosen: record the identified screening, prompt-size, retry and cache opportunities without changing the active pipeline.
- Why: the user requested an independent issue review; modifications require careful replay and output validation and the current evaluation is in progress.
- Undo: update the review after validating or rejecting each recommendation; run artifacts and code are unaffected.

## 2026-11-04: Run synthetic oracle alongside section 7 preparation

- Chosen: generate an oracle answer for each of the eight section 7.3 synthetic corpora, and pass its answer file to scoring; run the off-template planning step using its existing cache.
- Why: the user requested oracle attribution and the runbook's synthetic checks after the completed SciREX scoring.
- Undo: retain or set aside oracle and synthetic output folders; original corpora, labels and splits remain unchanged.

## 2026-11-04: Accept the legacy SciREX dataset predicate at query rendering

- Chosen: map the exact saved property-list form `; kg:dataset ?item` to the graph's canonical `ev:setting_dataset` predicate at runtime. Preserve saved plan text, explicit alternate `kg` namespaces, quoted text, comments, IRIs and other predicate names.
- Why: all fifteen saved SciREX first-line queries used a predicate that the graph never emits; a read-only probe showed the existing graph and unmodified list-for template already return dataset facts once that binding is corrected. This fixes the execution contract without changing prompts, gold labels or score definitions.
- Undo: revert the compatibility helper in `evidence/kg/query.py` and its three regression tests; the original plans and previous run artifacts remain available.

## 2026-11-04: Preserve SciREX query-fix provenance

- Chosen: record that fixed SciREX reruns started with the tested compatibility change in the working tree immediately before commit b713dea8; inspect their manifests before replay.
- Why: early manifests may identify the prior HEAD even though the query compatibility code was already present.
- Undo: retain the original outputs and regenerate new sealed runs from a clean checkout of the intended commit; do not rewrite existing manifests.
- Follow-up verification: all 30 fixed SciREX run manifests record commit 6b851988, which includes the compatibility fix b713dea8. The earlier timing concern did not materialize in these manifests.

## 2026-11-04: Run independent synthetic checks concurrently

- Chosen: run off-template, leak and the eight-corpus engine/baseline/oracle scoring sequence concurrently, keeping each sequence serial and each active sequence's cache separate.
- Why: the user requested parallel work and the allocation is time-limited; section 7 permits at most three long model steps at once and these sequences use separate run folders.
- Undo: stop the launch steps, retain all output and caches, and rerun the sequences serially using their existing caches.

## 2026-11-04: Preserve synthetic validator failures

- Chosen: retain the off-template and leak outputs and record their protocol/evidence-type validation errors without changing protocol definitions, prompt outputs or scoring.
- Why: q06/q10 resolve treatment and control to the same role, while leak scoring rejects the experiment type; changing these evaluation semantics mid-run would invalidate comparability.
- Undo: resolve the protocol mapping and domain type contract in a versioned change, then rerun with original question files and preserved outputs.

## 2026-11-04: Headline and answer-key split judge one line, by top-1

- Chosen: a rank or list question is scored on one plan line, `wholerun.scored_line` (a ranking: its first rank/best
  line; else the line asking the question; else the first line), by the headline and the split alike. An empty or
  failed scored line is an empty answer; the headline no longer falls through to a later line. The split judges a
  ranking by top-1, as the headline does. A failed scored line is labelled "plan error". The key records' metrics are
  renamed to the plan measure they name (`plan_metrics`, by `names.clean` over the measure id and its word-list names)
  before the key store is built.
- Why: the headline read the first answered line (scilead-17 and -27 scored top-1 from an unordered list line) while
  the split compared a whole ordered ranking on another line; and the key store kept the release's metric spelling
  ("F1", "ROGUE-1") while plan queries filter on measure ids ("f1"), so every metric-filtered line got an empty key
  answer and could only be labelled "synthesis error". Gold values, papers and the top-1 definition are unchanged.
- Cost if wrong: SciLead engine headline drops (estimated 0.136 to 0.045 reasoning on, 0.045 to 0 off); a run whose
  only useful rows sat on a later line now scores 0. A measure alias that cleans equal to an unrelated release metric
  would rename it wrongly.
- Undo: revert the commit; old run folders are untouched and rescore either way with no model calls.

## 2026-11-04: The plan check refuses what made lines fail or find nothing

- Chosen: `query_problem` refuses ev:/kg: terms the graph never emits (ev.ttl terms, the six kg: names,
  `ev:setting_<key>`, `kg:key_<key>` are allowed), so the planner's existing repair loop sees "the graph has no
  kg:dataset". `check_plan` also flags a line with no query, a `$metric`/`$metrics` line in a plan with no measure,
  and a plan whose things are all measures. `scripts/plan-runs.py plan` runs `check_plan` on every plan, prints
  `plan problems <id>: ...` and exits 1; it keeps the plan file. `planrun.run` is unchanged, so saved plans replay.
  The runtime `kg:dataset` shim stays for old saved plans only.
- Why: SciREX (15/15 plans used kg:dataset), scilead-05/-06/-19 (no measure), off-template q05/q09 (unplanned
  line), q06/q10 (only measures) and q08 (`ev:value`) all passed the old check and then failed or returned nothing.
  Of 104 saved plans, exactly these 39 folders are flagged; no saved template is.
- Cost if wrong: a valid query using a term added to the graph later is refused until `_KG_TERMS`/ev.ttl list it;
  the repair loop adds one planner call per refused query.
- Undo: revert the commit; plans and runs are unchanged.

## 2026-11-04: Old runs replay from their own commit (explicit, versioned break)

- Chosen: keep the extractor fingerprint as it is (it hashes `modelcall/call.py`), so the plain-text change gave
  the five llm_* extractors new ids. The lock fixture is versioned: `rag-factuality.v1.lock.json` (before
  7ca21081) and `.v2.lock.json` (now); a test pins that they differ only in llm_* ids. A replay whose recorded run
  used extractor ids this code does not build raises `replay.CodeChanged`, naming the ids and the run's
  `code_commit`, instead of a bare cache miss. Replaces "Preserve extractor fingerprint integrity" above.
- Why: an id alias table would let replay reuse cache entries across a code change; proving equivalence for every
  call costs more than it saves, and the old code is one `git worktree add` away. The runs Codex made on this
  branch already carry the new ids and replay as they are.
- Cost if wrong: replaying a pre-4-Nov run needs a checkout of its commit. Any later edit to an extractor source
  file (llm.py, llm_schema.py, screen.py, modelcall/call.py, gateway.py, pins.py, prompt.py, recording.py, the
  shared sources) changes ids again; this branch therefore leaves those files alone (item 11 is deferred for it).
- Undo: restore the single fixture and remove `CodeChanged`.

## 2026-11-04: Stale test fixtures, behaviour unchanged

- Chosen: `test_effect_scores_unchanged` no longer reads the record cache that run.json names by an absolute
  cluster path (monkeypatched to none), matching how its golden files were captured; the web app run-group test
  expects `...-cascade-gaps` (gaps is the default strategy since 750cd25e). Golden files unchanged.
- Why: both failed on `main` on Linux too; neither is a behaviour change.
- Cost if wrong: none for results; the golden test no longer covers token counts read from a live cache.

## 2026-11-04: Plan runs v2 (recorded setting `plan_version`)

- Chosen: `run_plan` writes `plan_version: v2`; a run.json without it replays as v1, byte for byte. v2: (a) a rank
  or best line's answer text starts "Best: <thing> in <paper> (score <s>)", ties listed; (b) a key literal in a
  query (`kg:key_<x> "…"`, `kg:contextKey "…"`) also matches its bracket parts, every name the plan's word list
  gives the thing it names, and graph keys whose own bracket part matches (`planrun.name_matcher`, no
  partial-word matching); a literal with nothing more renders as before; (c) no experiment map before the screen
  and none for a paper the screen left out; (d) a stage request clearly over the model's context window (chars / 4
  plus max_tokens) is not sent (`too_long`, noted as unchecked).
- Why: scilead-07 answered yes/no; "ICSI … (MRDA)" vs graph "mrda", "Ontonotes v5 - English" vs "ontonote 5.0",
  SciREX "named entity recognition ( ner )"; scilead-07 mapped 31 papers and 27 were screened out; one 327,338-char
  map request failed on every SciLead question. No prompt text changed: the word list already held the aliases.
- Cost if wrong: an alias the word list gives too broadly widens a filter (exact names only, so bounded); a
  screened-out paper loses experiments it would never have used; a request the estimate wrongly calls too long is
  skipped (the estimate is lenient: 4 chars per token).
- Undo: pass `plan_version="v1"`.

## 2026-11-04: A reply that never validates is not an outage

- Chosen: a `model_call` error whose every problem is "UnexpectedModelBehavior: Exceeded maximum output retries"
  or a context-window 400 counts as `model_failed`, not `service_failed`: `evidence run` warns instead of exiting
  2, and `--retry-errors` (extractor calls and stage calls) does not ask it again.
- Why: synthetic paraphrased (2 calls) and complex (1 call) exited 2 although the gateway answered: the model
  looped whitespace or quotes to max_tokens at temperature 0, so the same request fails again; the oversized
  SciLead map request was asked 16 times.
- Cost if wrong: a reply failure that a retry would have fixed stays failed until a new run folder.
- Undo: revert `rundir.permanent` and its uses.

## 2026-11-04: Off-template scoring plumbing

- Chosen: (a) the answer key is queried with the plan's sides mapped to the key's roles (`key_sides`: the role most
  key conditions named like the thing have); (b) names compare by `names.clean`, and a gold count-only column no
  plan column holds is not required when another gold column matches; (c) a question without a plan counts in the
  denominator as neither fresh nor a match; an unplanned line is not "fresh"; (d) a plan whose things are all
  measures gets treatment role `any` so its protocol validates.
- Why: the key store's sides are pack roles (baseline, rag, other), the plans' are thing ids, so side-filtered
  queries could never match; q02 returned "lawfactqa" for "LawFactQA"; q04 returned the right papers without the
  count; q06/q10 were silently left out of the denominator and q05 (no query) counted as fresh.
- Result on the recorded runs (no model calls): match rate 1/10 → 2/12, fresh share 4/10 → 3/12. The rest is a
  planner weakness (generic nouns such as "papers", "datasets" taken as compared things), left for a prompt change
  under docs/prompt-writing.md.
- Cost if wrong: (b) is more lenient than before; a gold count column is no longer checked when absent.
- Undo: revert the commit.

## 2026-11-04: Final-review fixes

- Chosen: (a) runs recorded on this branch before the `$metric` default (f3298676) or the kg:dataset shim (b713dea8)
  run differently even as v1; a mismatched replay now says so (`note`: recorded commit vs this one, replay from the
  recorded commit). (b) `name_matcher` widens only with the one thing the literal names, never through a name two
  things share, and a bracket part counts only when it is a short form (initials) of the rest ("(MRDA)", "( ner )",
  not "bert (large)"). (c) only "Exceeded maximum output retries" and context-window errors are permanent, not every
  UnexpectedModelBehavior (a proxy's bad body is passing). (d) the split's top-1 compares cleaned names as the headline
  does, and a v2 run's key query uses the same name matcher. (e) typed literals stay exact; the matcher's helper
  variables never reach the rows. (f) "Best: ..." comes from the first rank/best line with rows. (g) the cache reads
  whole lines only at start and its file lock waits at most 600 s, then names the lock file.
- Why: the whole-branch review found each case with a probe on the recorded runs or a small example.
- Cost if wrong: (b) a thing named only through a shared alias is not widened; (c) a truly hopeless malformed reply is
  asked again by `--retry-errors`.
