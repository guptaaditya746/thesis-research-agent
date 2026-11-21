# 3 Methodology

## 3.1 Research approach

This thesis investigates whether scientific question answering can be made more explicit and auditable by constructing an intermediate representation of evidence before answering a research question. The implemented system separates the identification of source statements and measurements from their integration and subsequent use. A result can therefore be examined at several levels: whether a relevant measurement was extracted, whether it was associated with the appropriate method and metric, whether an executable query selected it, and whether the resulting answer agrees with an external answer key. The motivation is methodological: a plausible answer alone does not identify which of these operations succeeded. A general claim that this separation improves scientific question answering requires empirical support and is not assumed here. [Citation needed: verified literature on scientific evidence retrieval and provenance-aware question answering.]

The study combines implementation analysis with controlled synthetic comparisons and a limited evaluation on real scientific datasets. Synthetic corpora supply explicit latent facts and source placements, permitting extraction, integration and study-direction evaluation. Real datasets test a more demanding path in which a natural-language question must first produce a valid plan. These experiments serve complementary purposes. Synthetic fixed-protocol execution tests the evidence engine under an already specified method; it does not test whether the system can independently design that method from an unfamiliar question.

Five research questions organize the investigation. RQ1 concerns end-to-end effectiveness relative to implemented BM25 RAG baselines. RQ2 concerns the availability and quality of structured evidence and provenance. RQ3 concerns the effects of component settings, including ontology reasoning. RQ4 concerns generalization across renderings, evidence arrangements and real questions. RQ5 concerns operational reliability and computational effort. These questions are addressed only to the extent supported by completed experiments. Human review, fresh-query reasoning and additional scientific domains remain unmeasured where the necessary experimental records are absent. The source basis for this chapter is recorded as E01–E26 in [the evidence inventory](evidence-inventory.md).

## 3.2 Overall architecture

The backend implements four principal layers: a model-call gateway, an evidence engine, evaluation components and a web application. The application invokes engine and evaluation operations; model-backed backend components call the gateway. Most processing occurs through Python modules within a backend process or its launched command, rather than through a separate network service for each stage. The served LLM replicas and GLiNER are external services. The implementation boundaries are visible in `backend/modelcall`, `backend/evidence`, `backend/evaluation` and `backend/webapp`.

The overall information flow is scientific papers → normalized document text → extracted evidence → linked evidence records → graph representation → executable evidence queries → structured results. In the question-planning path, the research question determines a plan, vocabulary and generated protocol before extraction. In the fixed-protocol path, an existing protocol specifies the extraction and deterministic synthesis directly. The order is therefore not a single universal pipeline in which planning always follows graph construction: a plan controls what evidence is sought and is later executed against the resulting graph.

The fixed-protocol entry point is `evidence run --protocol ...`; the planned path uses `evidence run --plan ...`. The engine exposes corresponding `run` and `run_plan` functions. The web application provides job creation, artifact viewing and planning interfaces through `webapp/evjobs.py` and `webapp/evplan.py`. Job outputs follow session directories for corpora, runs, scores, proposals and caches. A completed job and a correct scientific answer are separate outcomes. Exit status, recorded failures and score files must all be inspected.

A run persists its protocol, extracted items, checked calls, event stream, answer and graph. Planned runs additionally retain the confirmed plan, query results and the RDF record store. `graph.json` is a document/evidence graph useful for inspection; `records.nq` serializes the RDF representation used for structured querying. These files have related but different roles. Neither the presence of a graph nor completion of a process establishes that the represented evidence is complete or correct.

## 3.3 Document ingestion and preprocessing

### 3.3.1 Corpus representation

The execution contract consists of a `manifest.json` and the paper files it names. Each paper has an identifier, relative file path and SHA-256 digest. The engine reads textual paper content, conventionally Markdown, in manifest order. Baselines use the same manifest-and-paper contract. Ground truth is stored separately for evaluation; normal execution is not intended to read synthetic `ground_truth.json`. The explicitly named oracle-passage diagnostic is an exception and is not treated as an ordinary baseline.

Identifiers allow evidence and answers to be connected to individual documents without relying on generated descriptions. For SciLead, acquired papers use arXiv identifiers, including versions. SciREX preserves release document identifiers while converting token-based source material into text and character offsets. Distinguishing release size, locally available papers, tuning exclusions and question-specific coverage is necessary: a local corpus can contain more papers than a question's admissible answer-key subset.

### 3.3.2 Acquisition and conversion

`evidence/arxiv.py` implements acquisition through an ordered source ladder. It attempts structured LaTeX source and PMC XML where applicable, then HTML and PDF fallbacks. The LaTeX and JATS converters preserve usable text and table structure in Markdown. Docling converts HTML/PDF content, and the PDF table path also consults pdfplumber. Disagreements between table readers can mark cells as uncertain. Conversion failures and skipped documents are recorded rather than replaced with invented content. These capabilities are implemented, but the campaign does not provide a separate accuracy benchmark for every input format.

Acquisition metadata includes available titles, authors, dates, URLs, source formats and source hashes. A newly fetched demonstration corpus declares that it lacks the task-specific ground truth needed by the synthetic scorer. This designation should not be confused with a claim that a public dataset has no annotations: SciLead and SciREX have separate answer keys and real-set scoring adapters. Generic UI inventory questions over copied real papers are not automatically covered by those keys.

SciREX preprocessing reconstructs document text from tokens and section boundaries and translates annotation offsets into character spans. The converter checks that sections cover the source token sequence. Its type mapping interprets the release's `Material` category as a dataset for the scientific NLP evaluation. Such mappings are operational definitions of this implementation and should not be generalized to unrelated datasets.

## 3.4 Evidence extraction and graph construction

### 3.4.1 Typed extraction contract

Every extractor returns a common typed result containing evidence items, source spans, coverage and errors. An item's fields describe its scientific content, while links refer to other items. The core evidence roles include compared conditions or methods, metrics, measured values and author claims. Domain packs declare concrete types, fields, roles, units and protocol settings. General planned runs can also create experiment records, open claims and links between papers.

Extractor identity incorporates its version, source-code hash and configuration hash. This matters because a component name alone is insufficient to reproduce behavior: a modified prompt, model setting or schema can change its output. The engine writes the identities used by each run into its metadata and protocol lock.

### 3.4.2 Screening, cascades and gaps

The engine supports regular-expression, model tagger, single-call LLM and agentic extractors. A protocol determines the cascade available for each evidence type. In the `gaps` strategy used in the reported comparisons, screening first assesses whether a paper is relevant. The engine then starts with the initial extractor for each required type, merges its checked results and tests whether the study has enough evidence for the question. A missing condition, metric or usable pair identifies which evidence type should advance to its next extractor. Escalation ends when evidence is sufficient or the applicable cascade is exhausted.

This strategy operationalizes selective model use; it does not guarantee that the cheapest stage found all relevant evidence. The alternative `all` strategy runs every configured extractor and is useful for attribution experiments, but a matched all-versus-gaps comparison was not established in the audited campaign. Similarly, GLiNER is implemented and deployed, but the synthetic score reports inspected here list regex and LLM components. A healthy GLiNER endpoint is not evidence of a measured GLiNER contribution.

The engine also distinguishes tagger evidence confirmation from research-plan confirmation. With extraction confirmation set to `llm`, evidence found only by a model tagger can require confirmation by the LLM stage before it remains in the merged result. This is an extraction policy, not human approval of a research method.

### 3.4.3 Validation and merging

Central checks validate declared fields against their schemas, source anchoring, permitted span roles, extraction scope, numeric agreement with the quoted text and link consistency. A selector records the source file, content hash, character boundaries, exact quote and surrounding context. Rejected items retain reasons such as missing text, ambiguous anchoring, schema violations or dangling links. Accepted source anchoring proves that a passage exists in the recorded document; it does not prove the model interpreted its scientific role correctly.

Merging combines compatible items of the same type, preserving supporting spans and the extractors that found them. Normalization is defined by the merge implementation and pack configuration. Conflicting non-null fields can keep otherwise similar items separate. When a later extraction changes an item's identity, relinking updates references and records the correspondence. Remaining dangling links are counted rather than silently ignored.

### 3.4.4 Experiments, claims and relations

The experiment-mapping stage asks a model to identify experiments and their settings, such as dataset, model or population. Proposed experiments require an anchored source quote. Measurements can be assigned to an experiment through matching settings or a positional fallback. The fallback is a heuristic; proximity alone does not establish scientific association.

Open-claim extraction first identifies candidate sentences using the locked vocabulary and cue words, then reads each candidate into a claim record. A record includes subject, relation, optional object, setting, strength and an optional comparative direction. Relation grouping places equivalent verbs into groups and preserves unresolved verbs. Paper-link extraction and OpenAlex resolution are also implemented, with failed resolutions explicitly represented. These mechanisms support inspection, but the present controlled results do not validate unrestricted scientific relation extraction or citation-chain inference.

### 3.4.5 Graphs and synthesis

The JSON evidence graph represents documents and items as nodes, with document membership, item links and selected synthesis relations as edges. The RDF builder maps papers, experiments, things, metrics, values, comparisons, claims and links into the executable vocabulary. Values carry numbers and associations to things, metrics and experiments. Experiment settings appear as generated properties; helper properties encode normalized context keys and value positions. Comparisons are formed between different things measured on the same metric within an experiment, using metric direction where available.

Fixed-protocol effect synthesis selects usable treatment/control measurements according to protocol rules, including context matching and preferences such as table cells before prose. Arithmetic and categorical decisions are performed in code. An absent pair yields an explicit undetermined result with a reason. Author-claim agreement, duplicate indicators and effect flags are separate from the measurement-based direction. The resulting corpus label compresses the study outcomes; it is evaluated separately from per-study accuracy.

## 3.5 Query planning and structured execution

The planner decomposes a research question into evidence lines, identifies relevant things and measures, chooses a main-answer rule, proposes methodological decisions and creates SPARQL queries. It can start from saved templates or propose fresh queries. A separate critic flags decisions for review. The model proposes semantic structure, while deterministic code checks plan shape, required measures, allowed decision types, query parsing, template references and emitted graph vocabulary. Repair attempts can receive specific validation problems; failure remains an experimental outcome.

Methodological decisions remain explicit parameters. Supported main-answer rules include any line, all lines and a majority of lines. Query decisions can control matching requirements, counting units, thresholds and inclusion. Changing an approved decision changes the query parameters used at execution. A plan's readiness depends on confirmation records. `confirm_all` can stamp decisions with `system` for the automatic treatment; authentic human confirmation would require a person's own review record. All completed real-data runs in this campaign use automatic confirmation, and no human-confirmed comparison is reported.

Each evidence line executes separately. Its output records status, rows and readable text. A line that fails does not erase results from other lines. An empty successful query produces “No evidence found”; a failed query records a failure. These cases differ from a plan rejected before execution. Main-answer aggregation is implemented in `planner/lines.py`; ranking answers can name the best returned thing and paper. Planned answers are therefore structured query outputs and deterministic summaries, rather than unconstrained prose synthesis.

The assessment distinguishes structural validity, successful execution and task correctness. Passing validation only permits execution. A query may parse and reference legitimate predicates while still encoding the wrong research question or using a literal that matches no stored value. Conversely, an empty result can be scientifically appropriate when support is absent. Correctness must be judged against a matching task-specific key.

## 3.6 Ontology and reasoning

Ontology support operates at both pack and planned-run levels. The pack reasoner reads ontology labels and subclass relationships, uses `owlrl` to apply RDFS closure and derives broader-name relationships and link-type flags. This is RDFS-based processing; the use of an OWL-related library does not imply unrestricted OWL reasoning. Broader metric classes can allow a narrower known metric to satisfy an appropriately broader request.

For planned runs, field ontologies can contribute class labels and subclass edges to the record graph. Available sources include a computer-science fallback ontology and optional external CS-KG, MeSH and QUDT resources. Missing external resources have explicit fallback or no-tree behavior. Their contents and hashes are part of reproducibility: changing an ontology can change a graph even with the same extracted text.

A crucial experimental limitation concerns saved queries. Saved templates do not generally traverse the field ontology tree, so a nominal reasoning-on/off treatment need not exercise ontology-dependent querying. All scored main real-data queries in the current campaign were classified as template-based. Equality of their headline scores is therefore a limited implementation observation and cannot establish that ontology reasoning is ineffective. A causal test would require validated fresh queries whose answers depend on the relevant class hierarchy.

## 3.7 Experimental datasets

Table 3.1 describes locally available corpora and the samples actually evaluated. Counts of papers refer to corpus manifests, not original release sizes. Literature and licence details require final source verification before submission; no unverified permission to redistribute underlying papers is assumed. [Citation needed: verified dataset publications and release terms for SciLead and SciREX.]

| Dataset | Local papers | Evaluation units used | Ground truth and task | Coverage qualification |
|---|---:|---|---|---|
| SciLead | 31 | Ten corrected seed-0 questions; seven executable plans | Existing leaderboard rankings; best-paper top-1 | Missing source papers and tuning exclusions restrict eligibility |
| SciREX | 40 | Ten seed-0 questions; one executable plan | Existing dataset-name lists for scientific tasks | Release adapters and preserved split define eligible questions |
| Claude-rendered `rag-claude-s1-mixed` | 20 | One factuality question; 20 study directions per run | Latent facts, placements, study directions and corpus label | Previously used synthetic corpus; unseen status not established |
| Template-rendered `rag-tpl-s1-mixed` | 20 | Same factuality question and latent studies | Same latent study content and corpus answer, different text/placements | A paired renderer condition, not an independent dataset draw |

Direct read-only parsing identified 27 SciLead questions and 26 source-only SciREX questions. Filtering SciREX to the local corpus reduces its question list to 19. These counts do not describe the eligible evaluation pools after all tuning guards. The preserved question split lists 22 kept SciLead IDs and 15 kept SciREX IDs; paper-level exclusions also apply. The campaign used ten questions per set, not a full evaluation of every available question.

Both synthetic mixed corpora contain explicit, paraphrased, distributed, complex and contradictory renderings, with four studies assigned to each level. The generation metadata records seed 1. The Claude corpus records a Claude-family renderer and verifier; extraction and answering use Qwen. Cross-family generation reduces one direct source of shared-model bias, but does not demonstrate absence of benchmark exposure or synthetic regularities. The two corpora's latent `studies` and aggregate `answer` objects match, while their text and source placements differ.

CochraneForest was not available as a validated release/corpus for this campaign. SOFC-Exp and MeasEval source files were inventoried, but no valid controlled end-to-end comparison was established. Their layouts, labels and applicable tasks require validation. They are consequently outside the measured dataset set. Template-only multi-experiment and messy-table conditions described by the runbook are likewise not claimed as completed campaign experiments merely because generators exist.

## 3.8 Baselines

The evidence system is compared with global and per-paper BM25 RAG, implemented in `evaluation/baselines/rag.py`. Papers are divided at headings and paragraph boundaries into passages of at most 1,500 characters. Retrieval uses `BM25Okapi` over lowercase word tokens. Ties are resolved deterministically by paper identifier and offset.

Global retrieval selects eight passages across the corpus. Per-paper retrieval selects two passages from every paper, giving substantially broader document coverage. The settings therefore represent different evidence budgets, not equivalent-cost retrieval variants. Their default answer limits also differ: 4,096 output tokens globally and 16,384 per paper mode. These are upper bounds, not measured token consumption.

The answer call receives retrieved passages and returns text with citations. Citations that do not identify a retrieved passage are retained as dropped citations rather than accepted. A subsequent model call maps the free-text answer into the structure required by the scorer. For real questions this means rankings or name lists; for the synthetic factuality task it includes per-study directions and the aggregate label. Evaluation thus covers retrieval, generation and answer mapping together. Mapping errors are possible and should not automatically be attributed to retrieval.

Comparability checks require matching paper identifiers/hashes and the configured model identity between engine and real baseline runs. The same sample IDs and question text are used. The baselines have no permitted access to answer-key content during ordinary retrieval. Agent baselines and oracle diagnostics exist in the repository, but no additional controlled campaign result is reported without a corresponding completed score artifact.

## 3.9 Experimental protocol

The campaign root is `thesis-campaign-20261106T132128Z`. Its manifest records repository commit `4b39a245e2d83c3c877f947e99472ac0a96f245d` and submodule base `b962edd83c987efd1275ee535dd19bc4186e4ce3` with local modifications. The serving profile and patch were preserved. Later maintenance commits are distinguished in Section 3.11. This avoids attributing historical experiments to a newer clean checkout.

The serving model is `Qwen/Qwen3.8-27B-FP8`, revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, exposed as `orch-model`. Three replicas run on separate NVIDIA A100-SXM4-40GB Ampere GPUs on gammaweb07 under Slurm job 8827, as recorded in the campaign. The profile specifies a 65,536-token context limit and GPU memory utilization of 0.92. GLiNER uses `urchade/gliner_medium-v2.1`, revision `40ec419335d09393f298636f471328b722c6da9e`, sharing GPU 0. All replicas share the same weights; they are not three independent model families.

Real questions use seed 0 and the runbook's ten-question sample. An initial SciLead sample contained three tuning-question IDs and was rejected. The approved replacement retains exactly `scilead-03, -06, -11, -17, -18, -19, -20, -21, -22, -27`. The SciREX sample is `scirex-001, -004, -005, -006, -008, -010, -011, -017, -018, -019`. These lists are persisted in `scores/sample-10-corrected`. The scoring wrapper supplies exactly those questions and retains blocked cases in the denominator. No gold labels or invalid plans were repaired during evaluation.

Validated real plans were executed sequentially in reasoning-on and reasoning-off conditions. Each run can use three document workers internally; one experiment at a time does not imply one model request at a time. Reasoning-off runs reused matching model-call cache entries. Synthetic engine comparisons use three fresh-call executions per renderer. Claude baseline modes have three recorded executions each; template modes have two. Scoring the third template engine run against the first baseline outputs does not create a third baseline execution.

Run-specific extractor specifications record model settings, including temperature zero and seed 0 for inspected LLM extraction calls. These settings constrain sampling but do not guarantee identical served outputs. Preparation and planning calls have their own recorded contracts and should not be assumed to share every extractor setting. Fixed seeds are held constant across repeats to assess variation under the deployed configuration.

The full Linux suite had two recorded failures before the campaign and continuation was explicitly authorized. Those failures were not silently treated as passes. Service or schema failures remain visible in logs, stages and process exit codes. An unsuccessful execution is retained as an operational outcome; its missing answer is not invented as a valid semantic prediction.

## 3.10 Evaluation metrics

### 3.10.1 Extraction and integration

Synthetic extraction uses one-to-one matching of extracted items to compatible gold facts, implemented through a linear assignment procedure. Compatibility depends on type and content: examples include a compatible numeric value, condition role or metric identity. Span overlap and matching labels influence assignment cost. Numeric matching is not by itself a complete test of scientific association; the integration layer evaluates linked conditions and metrics separately.

For matched facts \(M\), extracted items \(I\) and gold facts \(G\), micro precision, recall and F1 are

\[
P=\frac{M}{I},\qquad R=\frac{M}{G},\qquad
F_1=\frac{2PR}{P+R}.
\]

The implementation reports undefined ratios separately where denominators are absent. Span accuracy is the share of matched pairs with a gold placement whose principal source span overlaps that placement. Integration measures include associations between matched measurements and their conditions/metrics, and whether the synthesis selected the intended treatment/control pair. Flag evaluation also reports precision and recall for such outcomes as author-claim disagreement; empty positive sets yield undefined ratios rather than manufactured perfect detection. Scores restricted to matched measurements must not be interpreted as completeness over all gold measurements.

### 3.10.2 Answer-level outcomes and denominators

Synthetic direction accuracy compares the predicted study direction with its determined gold direction. With \(D\) the set of gold-determined studies,

\[
A_{\mathrm{direction}}=\frac{1}{|D|}\sum_{i\in D}\mathbb{1}[\hat d_i=d_i].
\]

Completeness measures how many gold-determined studies receive a determined prediction; accuracy among answered studies uses that smaller denominator. Corpus-label correctness is a separate single outcome. A correct overall “mixed” label can coexist with incorrect or missing study directions.

Real SciLead questions use top-1 ranking correctness. The scorer also computes Kendall rank correlation on names common to predicted and gold rankings when at least two are available; this auxiliary partial-ranking measure does not replace top-1 or account for all omitted papers. SciREX questions in this sample use list F1, with precision and recall computed from matched predicted and gold names. The current scorer explicitly maps `list` to `f1`. Existing campaign prose labels the SciREX headline as recall, but inspection of code and question-level values establishes that it is F1. The chapters retain measured values and correct the terminology.

Let \(Q\) be the preserved sample, \(S\subseteq Q\) the successfully executed, scoreable engine cases, and \(s_q\) the task-specific score. The operational end-to-end headline is

\[
H_{\mathrm{E2E}}=\frac{1}{|Q|}\sum_{q\in Q}u_q,
\quad
u_q=\begin{cases}s_q,&\text{if a scoreable answer exists},\\0,&\text{otherwise}.\end{cases}
\]

This zero is a protocol-defined loss of useful output, not an assertion that a blocked plan generated an incorrect answer. The conditional diagnostic is \(H_{\mathrm{conditional}}=|S|^{-1}\sum_{q\in S}s_q\). It excludes blocked cases and is explicitly not substituted for the headline. The real scorer also records undefined metric cases and zeroes them in aggregation; both SciREX baseline modes have such a case for `scirex-019`.

### 3.10.3 Provenance, uncertainty and efficiency

Synthetic citation traceability measures overlap between cited passages and selected gold placement roles. It is a lexical/location proxy, not an entailment judgment. For real runs, the audited measure is availability of evidence source selectors and graph artifacts. The campaign has no labeled gold-evidence recall metric for the real samples, so selector coverage is not reported as evidence retrieval recall.

The statistics module implements 95% bootstrap intervals with 2,000 resamples and seed 0, using BCa where computable and a percentile fallback. Paired differences resample matched study or question rows. Degenerate data receive null bounds rather than invented certainty. Renderer variants share underlying studies and are not pooled as independent samples. No broad significance conclusion is based on three executions of one corpus.

Efficiency records include model calls, new versus cached calls, input/output tokens and recorded elapsed seconds. These support descriptive comparisons. They do not provide monetary cost, energy consumption or a complete amortized system cost. Planning, ingestion, tuning and preparation may be outside a run's reported total.

## 3.11 Reproducibility

Reproduction requires the recorded campaign version, preserved serving-profile modifications, corpus hashes, samples, protocols, plan decisions, ontology files and model pins. Each run stores a protocol lock with component identities and, where relevant, plan, word-list, ontology and tuned-step hashes. Events form a hash chain; sealed manifests list output digests. Replay support can rebuild compatible recorded runs from cached calls, while code or ontology changes can prevent exact reproduction. No claim is made that every campaign run was replayed successfully during this writing audit.

The writing checkout is root commit `645c8b0e2a11e99c25114900366902d025de713f` with `llm-setup` at `07762fe8fec53d2f5a4c58277934b9fc98be8f25`. These later commits document and preserve the Ampere deployment. The supported deployment uses the Pyxis/Enroot container image `pytorch/pytorch:2.8.0-cuda12.9-cudnn9-runtime`. Hugging Face cache settings are inherited from the cluster; users do not manually override the institution's cache variables. Container image naming alone does not provide an immutable image digest, and cache contents can differ by node. These remain environment dependencies.

A read-only audit prepared for these chapters verifies the paper hashes of the four evaluated corpora, primary sealed file hashes for the sixteen completed real condition-runs, and aggregate values against study/question rows in the inspected score reports. Its code and derived evidence are stored with the chapters. Integrity and traceability make examination possible; scientific correctness still depends on valid labels, suitable questions and careful interpretation of what each score measures.
