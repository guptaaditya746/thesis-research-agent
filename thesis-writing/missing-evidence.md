# Missing evidence and work needed before submission

The chapters are complete drafts of the evidence currently available, not a claim that all desired experiments have been completed. This document separates missing scientific evidence from editorial/source-verification tasks. No experiment, new model call, human confirmation or production-code change was performed as part of writing.

## 1. Highest priority: validate the real end-to-end pathway

The present SciLead headline is zero over ten questions, including seven executed cases; SciREX is zero with only one executed case. A scientific improvement claim requires a development investigation followed by an unchanged held-out evaluation, not selective repair of the reported sample. Preserve current runs as the original condition. Use independent development cases to determine whether the failures originate in screening, evidence extraction, experiment association, context normalization or query selection. Record expected intermediate evidence and the actual stage where it is lost. Do not revise questions or gold labels to make outputs match.

Specifically, investigate the missing best-paper evidence in `scilead-03`, the execution graph versus answer-key normalization issue in `scilead-17`, and the high-cost, empty-answer `scilead-21` run. Existing counterfactual error labels are insufficient for causal attribution. For each diagnostic, save the original source span, extracted record, graph triple and query binding, including explicit absence at each stage.

## 2. Planning validity and independent evaluation

Develop separate cases for absent measures, absent query text, unsupported predicates and structured response parse failures. Validate the complete planner-to-extractor-to-query contract rather than only syntax. Use development data to improve a bounded repair procedure, if a subsequent implementation task is authorized. Then evaluate on a prospectively fixed, family-isolated held-out sample, retaining every failed ID and all attempts. The currently reported validated subset must never replace the ten-question headline.

Question IDs in SciREX are generated from the filtered task list. Preserve the corpus manifest and exact question text as well as the ID; changing corpus availability can change which task receives a numeric ID. Recheck split membership against both question IDs and paper guards when material changes. `question-selection-audit.json` records the current sample checks; it does not prove historical absence of all development exposure.

## 3. Comparable baselines and computational budgets

The existing global and per-paper baselines are valid implemented comparators, but expose different amounts of text and use different answer token limits. A prospective budget-controlled comparison should hold model, question IDs, papers and evaluation mapping fixed while varying evidence access transparently. Measure answer quality together with total tokens, new calls and complete wall time, including planning and ingestion where appropriate. A new retrieval-size or budgeting feature would require a separate implementation experiment; it cannot be retroactively claimed as tested here.

Audit representative free-text answers against their mapped scoring structures to identify mapping losses. The existing scorer evaluates the combined retrieval–answer–mapping pipeline; it does not isolate each contribution. Do not introduce an LLM judge and describe it as exact gold scoring without validation.

## 4. Real evidence and provenance correctness

Current real provenance counts establish locator availability, not evidence recall, scientific association accuracy or entailment. Obtain authentic annotations or compatible existing gold for required measurements, method/metric/context links and supporting passages. Define the annotation unit and disagreement handling before evaluation. Conduct independent review where scientific interpretation is ambiguous. Such review requires genuine participants; automatic `system` confirmation is not a replacement.

Verify whether persisted selectors still resolve to the intended complete facts and whether returned query rows support the answer. Report false associations and missing evidence separately. Retain provenance availability as a structural measure even if semantic support is weak.

## 5. Ontology and human-confirmation ablations

The current on/off rows use template main queries and cached extraction. They do not test ontology-dependent fresh queries. Select development and held-out questions whose correct results require the ontology hierarchy, verify the loaded resource hashes, and inspect query traces proving treatment exposure. Compare identical extracted evidence where the question concerns query-time reasoning; use fresh full-pipeline runs if the question concerns its total computational effect.

Human confirmation requires authentic decisions by a reviewer on the specified questions, with timestamps and provenance. No such treatment is available. Do not manufacture it by changing the `confirmed_by` field or treating critic output as human review.

## 6. Generalization and independent corpora

Complete a documented unseen-vocabulary/leak evaluation using only permitted Claude-written corpora, with source/model exposure and tuned-step checks. Develop fresh off-template queries and preserve failed plans. Evaluate additional study families and questions; repeated calls on the same twenty synthetic studies do not provide independent dataset replication. Keep renderer variants and other shared-family cases together when splitting or pooling.

The paraphrased subset is an important failure condition, but four cases per rendering are insufficient for broad conclusions. Extend it with independently held-out content and annotation, retaining original latent facts and difficulty definitions. Multi-experiment and messy-table claims require their own completed results rather than assumptions from the existence of generators.

## 7. Additional real datasets and rights

CochraneForest requires a valid release, usable corpus, applicable licence and layout validation. SOFC-Exp and MeasEval require validated mappings from their source annotations to this system's task and evidence contracts. Source files alone do not establish compatibility. Confirm rights for the underlying paper texts separately from any repository software licence. Missing releases, rights or labels remain explicit blockers; do not fabricate substitutes.

## 8. Repetition, integrity and environment reproduction

The real comparison has no three independent repetitions, and template baselines have only two executions; third-engine paired scoring reused first-run answers. Additional repetitions should use new output directories and record cache reuse explicitly. Extend beyond the fixed corpus only after identifying independent evaluation units. Do not pool conditionally successful subsets or reused answers as extra observations.

Preserve the original dirty-submodule patch, exact serving profile, ontology files, dependency lockfiles and compatible source commits. Add an immutable container-image digest if available. Verify one compatible full replay with all required files before claiming replay success, and distinguish that from a fresh model replication. The writing audit checked primary output hashes, not every possible cache entry or a complete model-backed regeneration.

The recorded Linux suite had two failures: `backend/agent/tests/test_batch.py::test_sigterm_to_the_runner_process` and `backend/webapp/tests/test_evjobs.py::test_run_jobs_with_the_runbooks_groups`. Its source log records 3,092 passed, two failed and two skipped, with exit status 1. User-authorized continuation does not resolve these failures. Assess their implications in a separate maintenance task and preserve the original test result.

## 9. Reporting and bibliography

The original campaign prose and CSV label SciREX F1 as recall; the chapters use the executed scorer's F1 definition. Keep this discrepancy visible in the claim audit. Several earlier campaign paragraphs incorrectly state that real runs were not executed; rely on the later sealed artifacts and score files, not those stale statements.

Replace explicit citation-needed markers only with verified primary publications or authoritative source documents. Verify dataset descriptions, licences and provenance independently before final submission. The chapter-local evidence references are an implementation audit trail, not a finished scholarly bibliography. Select the final institutional formatting and convert equations/tables to LaTeX while retaining source paths or stable archival identifiers in supplementary material.

## Completion criteria for stronger conclusions

A stronger thesis would require a validated real-data execution path, a prospectively fixed held-out comparison with matched baselines, evidence-level correctness judgments, an ontology treatment actually used by fresh queries, and independent dataset/question coverage. Until those conditions are met, retain the present conclusion: promising controlled synthetic evidence processing, substantial real planning and execution limitations, and useful provenance instrumentation without demonstrated general scientific QA superiority.
