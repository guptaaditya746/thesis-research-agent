# Datasets and benchmarks for the proposed thesis improvement

**Recommendation, 6 November 2026.** This document selects evaluation material for [the proposed uncertainty-aware scientific QA method](impromement.md). No datasets were downloaded, converted, relabeled or evaluated for this task. Published dataset availability and readiness in this repository are different questions.

## 1. Recommended portfolio

Use a small portfolio that tests different scientific claims. Start with **SciLead, SciREX, QASPER and SciFact**, introducing the two new adapters sequentially. Use **MeasEval** as the first additional component benchmark when diagnosing measurement errors. SOFC-Exp and SciTab are useful later probes; CochraneForest is a promising biomedical extension requiring release validation.

All can be approached without an embedding model. Exhaustive processing means reading every required source unit in a declared corpus. It does not mean pooling every benchmark into one corpus or passing all documents in a single prompt. Original neural baselines may use embeddings; their presence does not require adopting those architectures.

| Priority | Dataset | Main evidence it could provide | Local readiness |
|---|---|---|---|
| 1 | SciLead | Correct ranking from scientific measurements; sensitivity to omitted best results | Adapter and historical controlled results exist. |
| 1 | SciREX | Entity identity, document-level relations and structured lists | Adapter and historical controlled results exist. |
| 2 | QASPER | Answer correctness, paragraph evidence and genuine unanswerable questions | New integration required; no completed local result established. |
| 2 | SciFact | Scientific support/refutation with rationale supervision | New integration required; no completed local result established. |
| Component probe | MeasEval | Quantity–unit–entity/property associations | Converter exists; limited scalar scoring needs careful scope. |
| Component probe | SOFC-Exp | Experiment frames and contextual associations in materials science | Converter exists; ranking labels are insufficient. |
| Later | SciTab | Compositional verification of scientific tables | New integration required. |
| Conditional | CochraneForest | Query-conditioned study conclusions and conflicting biomedical evidence | Publication verified; actual release, rights and local layout still need validation. |

The first two rows preserve continuity with [the measured thesis results](04-results.md). The new rows broaden what can be established; none automatically proves the method's novelty or guarantees publication.

## 2. Core datasets

### SciLead: test whether the right scientific result wins

The authors release curated task–dataset–metric–result annotations and scientific leaderboards. This is the closest match to the proposed `argmax`/`argmin` semantics. Use it to compare a flat exhaustive extractor, the current engine, and uncertainty-aware execution on identical papers. The [official project](https://github.com/UKPLab/emnlp2024-leaderboard-generation) links the dataset and original evaluation code.

The audited local corpus has **31 papers** and the historical campaign has a corrected ten-question sample; these are local counts, not the entire release. The existing [adapter](../backend/evaluation/realpapers/scilead.py) distinguishes numerical retrieval, linked metrics, top-paper ranking and pairwise ordering. Paper-best results do not provide a complete method-to-experiment ground truth.

Preserve top-1 correctness as the historical headline. Add candidate-winner containment and false stability only with a validated new scorer. Do not pretend a paper ranking establishes complete measurement extraction. Previously inspected questions are development/regression evidence; a new improvement claim requires an unexposed, paper-grouped selection where one is genuinely available.

### SciREX: test relational evidence instead of only numbers

[SciREX](https://arxiv.org/abs/2005.00512) was designed for document-level scientific information extraction, including salient entities and relations that cross sentences or sections. Its original labels are not a human-authored scientific QA collection. Distinguish official extraction metrics from the repository's derived list-question task.

The audited local corpus has **40 papers**. [The adapter](../backend/evaluation/realpapers/scirex.py) reads typed mentions, coreference clusters and n-ary relations, with dataset labels mapped from `Material`. Historical whole-run scoring uses **list F1**, not recall. Candidate-set containment, mention/cluster recall, and relation accuracy must have separate denominators.

Preserve original document and cluster identifiers through conversion. Corpus filtering can change generated question IDs, so freeze question text and corpus hashes as well as numeric IDs. Do not equate a salient entity absent from a selected relation with an irrelevant entity. This dataset is particularly useful for testing whether unresolved identity and attachment alternatives survive joins.

### QASPER: add evidence-grounded answers and abstention

The [original QASPER paper](https://arxiv.org/abs/2105.03011) reports **5,049 questions over 1,585 NLP papers**, with answers and supporting evidence supplied by practitioners. The [dataset card](https://huggingface.co/datasets/allenai/qasper/blob/main/README.md) exposes structured paper text and answer/evidence annotations, including unanswerable cases.

Use complete supplied paper content for each question. Keep answer types, multiple reference answers, paragraph identities and table/figure references intact. Reuse the official evaluation semantics for answer F1 and evidence selection rather than substituting an unvalidated LLM judge. Count unsupported visual evidence as a declared modality limitation; do not silently remove those questions after seeing failures.

QASPER is mainly **single-paper QA**. It can test incomplete evidence discovery and unjustified answers, but it cannot alone establish cross-paper ranking or corpus-wide synthesis. A new interface must produce its answer/evidence schema and map source selectors to original evidence paragraphs. Scanning only gold evidence would be an oracle diagnostic, not the primary condition. Group every question from the same paper into one split.

### SciFact: distinguish absent evidence from refutation

The [official SciFact repository](https://github.com/allenai/scifact) supplies claims, an abstract corpus, rationale annotations and evaluation tooling. Use the original verification task rather than an embedding-retrieval repackaging. Its [schema](https://github.com/allenai/scifact/blob/master/doc/data.md) preserves document IDs and sentence-level evidence sets.

Evaluate label prediction and evidence-supported correctness separately. Keep support, refutation and insufficient-evidence behavior distinct. A rationale set is an annotated supporting route, not necessarily a complete inventory of all scientifically relevant passages. A claim without annotated evidence is not automatically a universal fact about everything the supplied literature could establish.

Full-corpus exhaustive processing is a substantially larger workload than QASPER's one-paper setting. Pilot on development claims, estimate total corpus passes and cache reuse, then select a fixed labeled evaluation subset before execution. Do not shrink each claim's corpus to gold-containing abstracts. If a reduced corpus is necessary, publish it as a modified task with a frozen selection rule. The official test labels are withheld; use legitimate labeled splits or the official evaluation route, never invented labels.

## 3. Component benchmarks and later extensions

### MeasEval: prioritize this when values attach to the wrong entities

[MeasEval's official release](https://github.com/harperco/MeasEval) represents scientific paragraphs and annotations for quantities, units, measured entities/properties, context and relations. It is a focused test of full measurement tuples, not an end-to-end multi-paper QA dataset.

The existing [converter](../backend/evaluation/realpapers/convert_measeval.py) retains original annotations but exports only unambiguous scalar quantities to the simplified evaluator. Ranges and qualifiers can be excluded. Report excluded counts and preserve the original annotation task when comparing with official results. The existing [scalar checker](../backend/evaluation/realpapers/measeval.py) is not automatically the official SemEval score.

Use paragraph-scale exhaustive reading and exact offset validation. This is inexpensive relative to repeated full-corpus QA and can isolate whether quantity interpretation or relation attachment breaks the proposed uncertainty domains. Do not manufacture research questions merely to make this benchmark look like end-to-end QA.

### SOFC-Exp: experiment structure in another scientific domain

The [official corpus repository](https://github.com/boschresearch/sofc-exp_textmining_resources) describes **45 solid-oxide-fuel-cell publications**, experiment frames, entity types and slots. Entity/slot annotation coverage is concentrated in experiment-describing sentences; unannotated text must not automatically become negative gold.

The local [converter](../backend/evaluation/realpapers/convert_sofc.py) explicitly preserves missing value-to-material associations as `material=None`. Consequently, use experiment-frame/slot evaluation first. Do not generate “best material” labels from proximity or assumed joins. Those labels would require authentic additional annotation and comparability decisions.

Evaluate both the official annotation scope and a clearly separated complete-text pipeline, with sentence detection errors counted. Keep articles together across splits and preserve sentence-relative offsets. The benchmark is valuable for experiment associations even if it cannot support the desired ranking task.

### SciTab: a targeted test of tables and compositional checking

[SciTab](https://aclanthology.org/2023.emnlp-main.483/) contains expert-verified scientific claims paired with tables; the [authors' repository](https://github.com/XinyuanLu00/SciTab) provides the data format. It can probe numerical comparison, aggregation, contradictory interpretations and table-header dependencies.

Start from the supplied table and caption. This isolates reasoning from PDF extraction. A separate raw-PDF condition would require validated source alignment and a different protocol. Use the official label task and evaluator where supplied; do not claim exhaustive gold cell-level provenance unless annotations support it. Keep claims sharing a paper/table together across any custom split, and keep public reasoning traces out of inference input.

### CochraneForest: worthwhile, but validate before scheduling

A real [ACL 2025 paper](https://aclanthology.org/2025.acl-long.1359/) describes CochraneForest; its [PDF](https://aclanthology.org/2025.acl-long.1359.pdf) reports **202 annotated forest plots**, associated questions, study texts and study-specific conclusions. It would test conflicting evidence in a biomedical setting. Publication existence does not establish that this checkout has a usable release.

The local [adapter](../backend/evaluation/realpapers/cochraneforest.py) explicitly sets `LAYOUT_VERIFIED=False` and assumes a simplified `release.json`. Resolve release location, actual schema, document availability and applicable licences before using it. Do not describe the dataset as globally nonexistent or definitively unreleased based on the local gate. Do not recreate forest-plot labels or silently omit inaccessible studies while scoring against a complete-review conclusion.

## 4. Licence and provenance checks

These are observed source declarations or explicitly unresolved checks, not blanket permission to redistribute every underlying article. Save the precise downloaded release's licence and attribution requirements in its future manifest.

| Dataset | Verified declaration / remaining check |
|---|---|
| SciLead | [Project code](https://github.com/UKPLab/emnlp2024-leaderboard-generation) declares Apache-2.0 and links a separate data deposit. Dataset-deposit terms and individual paper rights require confirmation. |
| SciREX | [Repository licence](https://github.com/allenai/SciREX/blob/master/LICENSE) is Apache-2.0. Check the selected release and underlying article rights separately. |
| QASPER | [Publisher dataset card](https://huggingface.co/datasets/allenai/qasper/blob/main/README.md) declares CC-BY-4.0. Preserve attribution and identify the exact release. |
| SciFact | [Explicit licence file](https://github.com/allenai/scifact/blob/master/LICENSE.md): claims/evidence annotations CC-BY-4.0, abstracts ODC-By-1.0, code Apache-2.0. |
| SOFC-Exp | [Official README](https://github.com/boschresearch/sofc-exp_textmining_resources): manual annotations CC-BY-4.0, source articles described as CC-BY, code AGPL-3.0. Distinguish data use from incorporating their code. |
| MeasEval | Applicable data licence was not established from the inspected README. Confirm the release/task terms before importing or redistributing it. |
| SciTab | [Repository licence](https://github.com/XinyuanLu00/SciTab/blob/main/LICENSE) is MIT; confirm its scope for dataset files and third-party table content. |
| CochraneForest | Actual release/licence and included-study rights remain unverified here. Keep this integration blocked until resolved. |

No recommendation requires installing the original papers' embedding-based models. Reusing annotations or scorers does not imply adopting their inference pipeline.

## 5. Which novelty claim each benchmark can test

| Proposed capability | Strongest suggested test | Important limitation |
|---|---|---|
| Missing evidence changes the winner | SciLead | Gold paper-best rankings are not complete experiment semantics. |
| Ambiguous entity/experiment joins | SciREX; SOFC-Exp | Entity labels alone do not supply every needed relation. |
| Missing quantity context | MeasEval | Paragraph annotation does not establish corpus-level completeness. |
| Evidence discovery and justified abstention | QASPER; SciFact | Scope and annotation completeness constrain “no evidence” claims. |
| Table dependencies and numerical reasoning | SciTab | Supplied tables do not test ingestion robustness. |
| Conflicting study conclusions | CochraneForest, once validated | Requires usable release and correctly scoped biomedical interpretation. |
| Verification efficiency | Every eligible task, paired budgets | All conditions must share documents, questions and initial evidence exposure. |

None supplies ground truth for every proposed uncertainty state. New metrics such as false stability and candidate-set containment require validated mappings to the existing labels. Semantic provenance recall is unavailable wherever supporting spans or complete facts are not annotated. Mark it unavailable rather than deriving it from citation counts.

## 6. A resource-conscious execution plan

1. **Freeze the inventory.** Record release URL/revision, licence files, hashes, source counts, question IDs/texts, split membership, missing documents and annotation exclusions. Keep gold inaccessible to inference. Do not download anything until the permitted storage/cache mechanism is established.
2. **Use existing failures for development.** Diagnose the inspected SciLead/SciREX cases and validate conversion/scoring offline. Preserve all historical runs and denominators. Completed synthetic campaigns remain untouched.
3. **Add one adapter at a time.** QASPER first for answer/evidence behavior; SciFact next for support/refutation. Validate source offsets, schema and scorer equivalence before spending model calls. Add MeasEval as a focused diagnostic if tuple errors dominate.
4. **Run a small development pilot.** A proposed budget is ten questions/claims per new end-to-end task, seed 0, with all required documents for those questions. This is a debugging pilot, not a statistical superiority claim. Record complete token/call costs before projecting the larger campaign.
5. **Lock the held-out comparison.** Choose all eligible held-out questions or a prospectively justified sample; apply the same IDs to every system. Group by paper/study family, preserve official splits, and disclose known public-benchmark contamination limitations. A paraphrase of an inspected example is not an independent test.
6. **Compare the necessary controls.** Existing BM25 conditions, exhaustive map/reduce, exhaustive flat tuples, and the proposed method; include verification-order ablations. Record cold/warm caches and three fresh repetitions only when resources allow. Keep inference sequential on the existing Ampere stack.

For every dataset, report full-sample utility, conditional performance, answered/blocked/failed counts, evidence measures actually supported by its gold, and total cost. Use each task's correct metric; never average ranking accuracy, list F1, relation F1 and token F1 into an unexplained “overall accuracy.” Independent study groups, not repeated model calls, determine the effective statistical sample.

The scientific value comes from showing **where explicit unresolved evidence changes correctness, abstention or verification cost**, with matched exhaustive baselines. Adding more dataset names without validated mappings would weaken that argument.
