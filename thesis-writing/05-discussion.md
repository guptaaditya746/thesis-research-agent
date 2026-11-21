# 5 Discussion

## 5.1 Interpretation of principal findings

The principal finding is a marked difference between controlled synthetic evidence processing and the complete real-question workflow. With a supplied factuality protocol, the evidence engine recovered study directions more successfully than global BM25 RAG on the two mixed synthetic renderings. Its advantage was considerably smaller when the baseline retrieved passages from every paper. On the corrected real-data samples, the engine produced no correct SciLead top-1 answers and no positive SciREX list F1, while many questions failed plan validation before execution. The results therefore support a narrow capability claim about structured processing of specified evidence, but not a general claim of superior end-to-end scientific question answering.

This distinction matters because the experiments exercise different parts of the system. A fixed protocol provides evidence types, matching rules and synthesis policy in advance. A real question requires the planner to identify measures, choose useful query structure and connect those choices to what the graph actually stores. Strong performance after a protocol has been supplied does not validate those preceding decisions. The real experiments expose this gap directly rather than treating it as a separate implementation detail.

A second finding is that inspectability and correctness can diverge. Completed real runs retained source selectors, graph records and query traces even when their headline answers were wrong or empty. Such records make failure analysis possible, but they do not turn the result into a correct answer. The system's value as an auditable experimental instrument must therefore be distinguished from its current task effectiveness. All interpretations below refer to the evidence identifiers in [the inventory](evidence-inventory.md) and the measurements in Chapter 4.

## 5.2 Comparison with RAG

The synthetic global baseline selected only a small number of passages from the entire corpus. Its low study-direction accuracy was accompanied by low completeness, while its aggregate answer could still correctly describe the corpus as mixed. This is consistent with an evidence-budget limitation for a task that requires coverage of many studies. The experiment does not establish that BM25 is generally unsuitable for scientific retrieval; it evaluates a particular top-eight-passage configuration against a corpus-wide study accounting task.

The per-paper baseline provides a more informative challenge. By retrieving from every paper, it substantially reduced the engine's observed advantage. The paired intervals for the first-run engine-minus-per-paper differences included zero in both renderings. The data therefore support the proposition that document coverage is an important part of the observed gap. They do not isolate a causal contribution from graph representation, deterministic synthesis or extraction alone, because all of these differ simultaneously between engine and baseline.

Computational effort further limits the comparison. The engine makes repeated extraction and checking calls, while the baseline answers once and maps that answer to a scoring structure. The first Claude engine run used many more recorded tokens than either baseline. A useful methodological contribution may justify additional computation, but that trade-off must be measured explicitly. The present results compare delivered performance under existing configurations; they are not evidence of a quality gain at equal latency, token budget or monetary cost.

The real-data results reverse the synthetic comparison. Global RAG obtained correct SciLead rankings where the engine either failed to produce a valid plan or failed after execution. Per-paper RAG was weaker than global on this sample, showing that exposing more source text does not automatically improve a generated answer. Potential explanations include evidence dilution and generation or mapping errors, but the aggregate scores alone cannot identify which explanation applies. The justified conclusion is that the implemented evidence system underperformed these baselines on the evaluated real questions. Broad superiority claims are contradicted by that observed sample.

## 5.3 Planning as a bottleneck

Planning coverage was substantially higher for SciLead than SciREX, but remained incomplete for both. The missing-metric SciLead plan shows a direct interface failure: a query required a measure that its own plan did not identify. Missing-query cases and response parse failures show other routes by which a natural-language question failed to become an executable method. These outcomes are methodologically significant because they reduce end-to-end utility before extraction can begin.

The validation gate nevertheless serves an important protective role. Executing a query known to be absent or inconsistent would make a completed process appear more successful without increasing scientific validity. Preserving blocked plans allows the headline denominator to reflect the system's coverage while avoiding fabricated answers. Reporting conditional performance alongside that headline then asks a different question: given that the planner produced a usable plan, how well did execution perform? In this campaign the conditional engine score also remained zero on both real datasets, so planning coverage alone cannot explain the lack of correct outputs.

Historical unsupported `kg:dataset` queries demonstrate a vocabulary mismatch between query generation and graph construction. This is a concrete form of planner–executor misalignment. However, the fresh no-query cases cannot all be attributed to that relation merely because it occurred previously. Their retained validation records establish an absent query, not its underlying cause. A defensible analysis must preserve that uncertainty rather than assigning a convenient common explanation.

The larger design issue is alignment among three representations: what the question asks, what extraction produces and what the query can select. A query can be syntactically valid and use supported predicates while still selecting an empty or inappropriate subset. Likewise, many valid extracted facts can fail to satisfy a restrictive query. The expensive `scilead-21` run illustrates this possibility: a large evidence record set did not yield answer rows. Future work should inspect the transitions between these representations with fixed development cases and explicit contracts, rather than optimizing only for query parse success.

## 5.4 Generalization

Synthetic data provide controlled access to ground truth that is difficult to obtain for complete scientific documents. Their explicit measurements and source placements make stage-specific errors observable. Using different renderer and extraction model families also avoids evaluating only whether a model can read text generated by itself. These are useful design features, but they do not make the corpora representative of scientific literature.

Both evaluated synthetic corpora share the same latent study content and overall question. Their comparison isolates one form of rendering variation. The four paraphrased studies were notably weaker for the engine than the other mixed-corpus subsets, especially in the template rendering. This is evidence of sensitivity to expression within the tested cases, even though their intended facts were unchanged. It is not a reliable ordering of general difficulty across paraphrase, contradiction or distributed evidence, because each subset is small and the cases are not independently sampled collections of research questions.

The corpora were also present in prior checked-in evaluation material. No new tuning during this campaign was observed, but historical development exposure cannot be excluded. Consequently, the measured synthetic performance should be treated as known-corpus capability evidence. An unseen-vocabulary claim would require the runbook's separate leak-split design, restricted to Claude-written corpora and accompanied by exposure checks. That experiment is not established by the current campaign's mixed-corpus results.

Real SciLead ranking and SciREX list questions extend the task space beyond one fixed factuality question, but coverage remains narrow and incomplete. Neither biomedical review synthesis nor materials/measurement extraction has a completed controlled comparison here. The thesis can describe the adapters and intended workflow without claiming demonstrated cross-domain effectiveness. Additional domains would strengthen external validity only after their corpus completeness, annotation mapping, licences and task definitions have been validated.

## 5.5 Provenance and reproducibility

The implementation offers concrete traceability mechanisms: source selectors, extractor identities, stored model calls, query rows, event chains and manifests. These mechanisms support several practical questions about an output. A reader can determine which recorded text was used, identify the extraction component and inspect which query selected the result. Failed or unresolved stages can remain visible rather than being represented as an unsupported negative conclusion.

However, provenance guarantees must be stated precisely. A selector with a file, offset and hash is an addressable record of evidence. It does not certify that the selected passage supports the attached scientific interpretation. A graph with many triples is a representation of extracted assertions, not an independently verified knowledge base. A valid hash chain detects certain inconsistencies relative to recorded hashes; it does not establish that the original extraction or annotation was correct. No independently signed integrity guarantee is claimed.

The results make this distinction tangible. All audited real evidence items had locator fields, yet engine accuracy remained zero. Similarly, high synthetic citation overlap did not imply comprehensive or correct study-level baseline answers. Provenance availability is therefore a necessary diagnostic resource for this design, but the campaign does not establish its sufficiency for trustworthy answers. Semantic evidence support, relation correctness and completeness need separate judgments or matching labels.

Reproducibility is strongest at the level of persisted inputs, configurations and outputs. Corpus hashes and retained samples identify the evaluated material, while model pins and protocol locks constrain the intended computation. Exact regeneration is less certain. The original campaign used a modified submodule, later maintenance commits differ, external ontology files matter, and the container reference is a tag rather than a verified immutable digest. Live model execution can vary even with fixed seeds. Cached reconstruction and fresh experimental replication should consequently be treated as different objectives.

## 5.6 Impact of reasoning and ablations

The observed reasoning-on/off equality provides little evidence about ontology utility because the completed real main queries used saved templates. Those templates do not exercise the ontology tree in the way a fresh hierarchy-aware query could. Cache reuse further means that the two conditions share model-produced intermediate work. This reuse can help hold extraction behavior stable for an execution-level comparison, but it is not an independent repetition of the complete pipeline.

A meaningful reasoning experiment should first establish that the selected questions require a relation supplied by the ontology. It should then verify that the relevant tree was loaded, that query execution used it and that removal changes the intended information pathway. Without these checks, a setting named “reasoning on” is an inadequate operational definition of the treatment. The present finding is limited to unchanged headline outputs for the evaluated template queries.

No authentic human-confirmed comparison was found. Automatic system confirmation cannot stand in for a person's review, and a critic's flag is not proof that a human resolved the issue. Likewise, deployment of GLiNER or implementation of agentic extractors does not demonstrate their incremental benefit. Those claims require matched comparisons that hold questions, corpora and other settings fixed. They remain proposed experiments rather than demonstrated contributions.

## 5.7 Threats to validity

### 5.7.1 Construct and measurement validity

The evaluations measure different constructs. Synthetic extraction F1 measures compatible fact matching; direction accuracy measures study-level interpretation; SciLead top-1 measures best-paper selection; and SciREX F1 measures answer-name overlap. None directly measures unrestricted answer quality. Combining them into one accuracy would obscure their denominators and meanings. Correct aggregate labels are particularly coarse and can mask missing study evidence.

There are also limitations within individual metrics. Source-overlap measures do not establish entailment. Association scores conditional on matched measurements exclude missed facts. Undefined precision for an empty answer can produce undefined F1, which the real headline zeroes. The audit's correction of the SciREX metric label demonstrates that narrative summaries can diverge from code even when the stored numbers are unchanged. A thesis must define its metric from the executed implementation and verify representative rows.

Automated failure attribution has similar limits. The `scilead-17` diagnostic shows that formatting differences can affect a counterfactual answer-key query. Its synthesis-error label therefore cannot be accepted as a unique causal diagnosis. Stage categories should remain provisional until replay and record inspection establish where useful evidence was lost.

### 5.7.2 Internal and statistical validity

The corrected sample protects against the detected question-level tuning overlap, but does not prove complete historical isolation. The initial invalid sample remains excluded. The preserved split combines question and paper constraints, and synthetic corpora have prior repository exposure. No claim of uncontaminated unseen evaluation follows merely from using seed 0 or a directory named “test.”

The samples are small. Ten real questions and twenty synthetic study decisions provide limited precision, particularly when only one SciREX plan executes. Repeated executions on the same questions do not increase the number of independent scientific cases. Renderer conditions share their latent studies and must not be pooled as independent observations. Bootstrap intervals describe sampling variation under the chosen resampling assumptions; they do not remove annotation, exposure or selection biases.

The template third-run baseline outputs were reused, so they provide no additional baseline variability measurement. Even fresh-call repeats share weights, prompts, hardware and source material. The observed score stability cannot establish robustness to different models, domains or deployments. The two recorded offline test failures also limit claims about overall implementation reliability despite authorized continuation.

### 5.7.3 External validity and resource dependence

The available real corpora cover only part of their broader scientific domains. Missing documents can restrict questions and alter eligible comparisons. Raw SOFC-Exp and MeasEval files have not become validated campaign corpora, and release/licence requirements constrain CochraneForest use. Missing labels or permissions cannot be replaced by synthetic assumptions.

The serving configuration is specific to the Webis cluster, pinned Qwen weights and Ampere hardware. Context limits, extraction chunking, shared-service load and cache reuse affect observed effort and possibly outcomes. Run-level latency excludes parts of preparation and does not represent a fully amortized deployment cost. The results cannot be generalized to other models or larger corpora without further measurement.

## 5.8 Limitations and future work

The immediate priority is a development investigation of the real workflow's representation boundaries. Missing metric declarations, absent queries, schema parse failures and empty-result queries should each have separate diagnostic cases. Improvements should be evaluated on development material before applying an unchanged protocol to a new held-out sample. The current zero results should remain part of the thesis record rather than being overwritten by later repaired runs.

A second priority is evidence-level validation on real scientific text. Authentic judgments or suitable existing annotations should identify required measurements, their conditions and experiment associations. This would permit separation of retrieval/extraction recall from query selection and answer synthesis. Until such labels exist, locator availability should remain a structural measure.

Further comparisons should control document exposure and computational effort. Per-paper RAG is a useful starting point because it addresses one major coverage limitation of global retrieval, but the current answer caps and evidence budgets differ. A prospective experiment could compare fixed retrieval budgets and report quality alongside tokens and latency. Any new retrieval option would be a future implementation change, not an evaluated feature of the present campaign.

Meaningful ontology ablation requires fresh queries, while human-confirmation experiments require authentic review. Generalization requires study-family isolation, exposure tracking and additional question structures on validated corpora. Reproducibility would be strengthened by preserving immutable container identification, complete dependency versions and compatible replay bundles, followed by both cached integrity checks and fresh reruns. These are recommendations derived from observed gaps; none is presented as already completed work.

## 5.9 Research question synthesis

| Research question | Evidence-based assessment | Scope of conclusion |
|---|---|---|
| RQ1: End-to-end effectiveness | Supported narrowly on synthetic fixed-protocol comparisons against global RAG; broad superiority contradicted by the observed real samples | Per-paper synthetic intervals include zero; real engine utility is zero in both samples |
| RQ2: Structured evidence and provenance | Availability supported; semantic adequacy remains inconclusive | Located evidence and graph artifacts exist, but real gold-evidence recall and entailment are unmeasured |
| RQ3: Component ablations | Inconclusive | Template on/off equality does not test ontology-dependent fresh queries; human and extractor component effects unmeasured |
| RQ4: Generalization | Limited rendering capability supported; broad real-world transfer not supported | Shared synthetic truth, prior exposure, paraphrase failures and low real planning coverage constrain inference |
| RQ5: Reliability and efficiency | Instrumentation and substantial failure costs demonstrated; efficiency advantage not established | Calls, tokens, failures and timing are recorded, but repeated real runs and complete cost accounting are absent |

The defensible thesis contribution is an implemented and inspectable evidence-processing workflow with controlled evidence of capability and documented limits. Its experimental record supports further investigation of structured scientific retrieval, while clearly identifying the planning and representation failures that currently prevent a broader effectiveness claim.
