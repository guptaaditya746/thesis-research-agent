# Claim audit

Audit date: 6 November 2026. Scope: `03-methodology.md`, `04-results.md` and `05-discussion.md`. Sources and source hashes are recorded in `verified-evidence.json`; exact question selection checks are in `question-selection-audit.json`. This audit is a scientific writing check, not a new model evaluation. Status **verified** means supported at the stated scope; **partial** means the text must retain a qualification; **unsupported** means excluded as a positive finding.

## Methodological claims

| Claim / chapter section | Status | Evidence and audit decision |
|---|---|---|
| Shared extraction engine supports fixed protocols and generated plans (§3.2) | Verified | `engine.run`, `engine.run_plan`, `planrun.run`; both kinds of persisted output inspected. Do not describe fixed-protocol results as full planning results. |
| Manifest plus hashed text is the execution input (§3.3) | Verified | Corpus loader and baseline `SystemCorpus`; all paper hashes of four evaluated corpora checked. |
| Structured acquisition ladder and uncertain-table handling (§3.3) | Verified implementation; empirical accuracy partial | `arxiv.py`, `sources/`, `tables.py`; no separate campaign benchmark of ingestion formats. |
| Typed, anchored evidence and gap escalation (§3.4) | Verified implementation | `contract.py`, `checks.py`, `merge.py`, `engine.py`; run specifications match gaps/cascade configuration. Semantic interpretation remains fallible. |
| Experiment, claim and link stages exist (§3.4) | Verified implementation | Corresponding modules and real stage reports. No universal relation completeness or successful external resolution claim retained. |
| JSON graph and RDF store are distinct (§3.4) | Verified | `graph.py`, `kg/build.py`; both primary output hashes checked for real runs. |
| Plan validation and confirmation (§3.5) | Verified | `check_plan`, `confirm_all`, `check_runnable`; all audited executed decisions stamped system. No authentic human treatment claimed. |
| Answer generation for plan runs is structured/rule-based (§3.5) | Verified | `planner/lines.py`, `planrun.answer`; line rows and deterministic answer shape inspected. No autonomous free-form synthesis claim. |
| Ontology closure is RDFS and templates limit treatment (§3.6) | Verified implementation and scoped result | `DeductiveClosure(RDFS_Semantics)` and real generality reports. Full OWL reasoning and beneficial ontology effects are not claimed. |
| BM25 retrieval budgets and mapping (§3.8) | Verified | `K`, `MAX_CHARS`, `MAX_TOKENS`, `retrieve`, `rag_real_full`; raw baseline settings checked. Retrieval budget equality is not claimed. |
| Original code/environment versions (§3.9–3.11) | Verified recorded metadata; exact regeneration partial | Campaign manifest, sealed run commit, saved profile/patch and current Git hashes. Dirty state and mutable container tag explicitly limit reproducibility. |
| Error/blocked handling (§3.10) | Verified | Scorer maps missing runs and undefined headline metrics to zero. Chapters distinguish protocol utility from fabricated answers. |

## Numerical and experimental claims

| Claim / sections | Status | Primary verification |
|---|---|---|
| Four corpus sizes 31, 40, 20, 20 (§3.7, §4.2) | Verified | Counted manifest paper entries and checked paper hashes. These are local counts. |
| Real source-question counts versus filtered/kept pools (§3.7) | Verified with stated filtering | Direct read-only calls to `_real_questions`; split files and selected text/IDs checked. Source-only SciREX count must not stand in for local-corpus count. |
| Corrected ten-question samples, no sample tuning-question overlap (§3.9, §4.2) | Verified for current material | Exact lists match score reports and preserved kept-question sets; direct paper guards and baseline/plan question text checks. Historical synthetic exposure remains unresolved. |
| Engine synthetic direction scores .90/.95/.95 and .80/.80/.80 (§4.3, §4.6) | Verified | Recalculated from synthesis study rows in six engine reports, not copied from campaign narrative. |
| Synthetic baseline means and paired intervals (§4.3) | Verified reported statistic | Per-mode score reports, same study IDs and no excluded IDs. No assertion of superiority against per-paper RAG when intervals span zero. |
| Corpus label mixed correct for first comparisons (§4.3) | Verified | Both first-mode reports' `label_correct`, separate from per-study accuracy. |
| Extraction counts, P/R/F1, span accuracy (§4.3) | Verified reported score; construct limited | `extraction.rows` values and matching code. Span accuracy is conditional; numeric matching does not certify complete scientific facts. |
| Integration sixty-five/fifty-four matched values and .70/.60 true-pair rates (§4.3) | Verified reported score | First Claude/template integration rows. No completeness inference from perfect matched-link accuracy. |
| SciLead engine 0/10, global 6/10, per-paper 2/10 (§4.4) | Verified | Per-question rows agree with means; seven executed sealed runs per condition. |
| SciREX engine zero, baselines .05/.078571 (§4.4) | Verified **F1**, not recall | `HEADLINE['list']='f1'`; mean rechecked over ten rows including explicit undefined-to-zero case. |
| Question-level real tables (§4.4) | Verified | Exact IDs, headline values, missing-run flags and undefined F1 from both wholerun reports. |
| Conditional engine zero over seven/one executed cases (§4.4) | Verified | Conditional artifacts and complete seals with successful call records. Never substituted for headline. |
| Planning 7/10 and 1/10; category counts (§4.5) | Verified | Both validation JSONs; one missing metric, nine missing-query cases across sets, two parse/generation failures. No-query causes not presumed. |
| Five synthetic levels, four studies each (§4.6) | Verified | Synthesis `rows` and corpus generator metadata; grouped within one mixed corpus, not separate question benchmarks. |
| Real on/off headline equality (§4.6) | Verified observation; causal explanation partial | Both score rows; all scored main queries templates; off-run new calls zero. No claim of a valid fresh-query ontology ablation. |
| Third template baseline repetition (§4.6) | Unsupported; explicitly excluded | Manifest says first baseline answers reused. Table reports only two executions. |
| Real evidence 788/37 records and 7,341/191 N-Quad lines (§4.7) | Verified structural counts | Recounted primary files and compared with provenance report. Duplicate evidence across questions possible. |
| All real items have spans/selector keys (§4.7) | Verified availability | Recounted all on-run evidence; not a semantic check or gold-evidence recall. |
| Synthetic citation overlap (§4.7) | Verified proxy | First-run synthesis rows and scorer's placement-overlap definition. No entailment claim retained. |
| S007/S017 missing-evidence reasons (§4.8) | Verified recorded reasons | First Claude answer and confusion data; they are undetermined, not wrong determined directions. |
| Three extraction/four synthesis labels and one SciREX synthesis label (§4.8) | Verified as scorer labels only | Real wholerun summary plus `truthgraph`/`error_split` code. Attribution validity is qualified. |
| Apostrophe issue and absent best-paper diagnostics (§4.8) | Partial causal support | Retained query-replay note and raw plan/answer values. In-memory gold replay is not a production fix or a replaced score. |
| Model-call counts, tokens, seconds (§4.9) | Verified recorded aggregates | Summed run.json and raw real baseline call records; fresh-call counts distinguished from cached computation. No total campaign cost claim. |
| Two offline suite failures (§3.9, §5.7) | Verified historical test result | `evidence-general-prep-20261106/logs/linux-pytest.log`, `.exit`: exit 1, two named failures. No new full suite was needed or run for prose-only changes. |

## Interpretations and unsupported findings

Chapter 5 interprets measured outcomes with conditional language. A large synthetic advantage over the tested global baseline is supported. A broad advantage over RAG is unsupported and conflicts with the real samples. Better document exposure is a plausible explanation for the per-paper baseline improvement; it is not isolated causally by these comparisons. Planning is a coverage bottleneck, but conditional real scores establish additional downstream problems. Source locator availability is demonstrated; correct scientific support, exhaustive evidence recall, unrestricted knowledge-graph completeness and trustworthy automatic reasoning are not.

Human-review benefit, ontology benefit on fresh questions, GLiNER's incremental effect, unseen terminology recall, general off-template success, cross-domain medical/materials effectiveness, monetary savings and three independent template-baseline repetitions are excluded as positive claims. Their missing evidence is listed separately.

## Corrections made during writing

The drafts replace the earlier SciREX recall label with F1 without changing any score artifact. They distinguish source-only from corpus-filtered question availability, the current campaign from historical rescores, and original campaign commits from later serving-maintenance commits. They retain all blocked questions in the operational headline and explicitly mark undefined F1. They replace stale “no real execution” statements with current sealed-run evidence. They do not promote the answer-key apostrophe diagnostic into a proven explanation of the production answer.

## Final quality checks

The numerical audit covers thirteen synthetic reports, both real report sets, forty real baseline answer records and sixteen sealed real runs. It additionally inspects ten raw synthetic baseline answer artifacts and checks six synthetic engine seals, primary hashes and fresh-call counters. Corpus source hashes, selected question identities, paper-level guards, primary artifact hashes, completion state and recorded call status were inspected. Equation definitions were compared with the scoring implementation. Cross-chapter terminology uses study-direction accuracy for synthetic comparisons, top-1 for SciLead and list F1 for SciREX. Local Markdown source links and required section coverage were checked. The initial writing-audit assertion used the wrong lock filename and was corrected to the implementation’s `protocol.lock.json`; the subsequent audit passed. A parser check initially supplied the SciREX directory where the API requires `test.jsonl`; the corrected read-only check passed and established the source-only/local filtering distinction. Claims requiring an external scholarly source remain explicit citation-needed markers rather than fabricated references.

The audit does not certify every log line, every output beyond the named primary hashes, every source quote's scientific meaning, or independent fresh reproduction. Those boundaries are preserved in the chapters. No production code, gold labels, datasets, prior experimental outputs, Slurm services or Git remotes were modified for this writing task.
