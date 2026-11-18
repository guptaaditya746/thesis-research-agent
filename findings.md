# Findings: realistic synthetic research papers with exact hidden facts

Method: 5 parallel web searches → 21 sources opened → 99 claims extracted → 25 claims checked by 3 independent checkers each (23 confirmed, 2 refuted). Tags: **[verified]** = a research agent opened the page and quoted it; **[verified, 3-vote]** = additionally confirmed 3-0 by adversarial checkers; **[unverified]** = seen only in search snippets. "Suggestion:" marks our own ideas, not claims of the source.

## Summary: most useful ideas, ranked

1. **Measure before fixing: treat the classifier as a two-sample test and add a surface-form baseline.** Formatting/structure features alone reach AUROC 0.93–0.995 on standard detection sets, so AUC 1.0 may be mostly cues like system names and missing citations. Source: Dutta Chowdhury et al., EMNLP 2026 Findings; Lopez-Paz & Oquab, ICLR 2017. Cost: code only. Risk: hiding cues fixes the test, not the text.
2. **Few-shot with retrieved real passages.** Stylistic examples and retrieved context were the calibration methods that consistently lowered a trained classifier's accuracy; personas and fine-tuning did not. Source: Pagan et al., arXiv 2511.04195. Cost: prompt change. Risk: realism and fidelity trade off; copying real wording.
3. **Slot templates: LLM writes prose with placeholders, code fills and checks numbers.** Source: ASPIRO (arXiv 2310.17877), FACTS (arXiv 2510.13920), RIKER (arXiv 2601.08847). Cost: prompt change + code. Risk: LLM still mangles some slots (FACTS ~2% render errors), so keep the blind recovery check.
4. **For templates: many varied templates or template-then-rewrite, or exact fact sentences inside real background text.** Source: TempLM (arXiv 2205.11055), Kasner & Dušek (arXiv 2203.16279), BABILong (arXiv 2406.10149). Cost: code / extra model calls. Risk: planted sentences stand out (BABILong admits this).
5. **Preference tuning (DPO/RL) of an open model against the classifier.** Source: Nicks et al., ICLR 2024; Pedrotti et al., arXiv 2505.24523. Cost: fine-tuning on GPU. Risk: fools that classifier only; in-domain classifiers barely move (RoBERTa 1.00→0.97 on arXiv abstracts); facts may drift.

---

## Q1. Systems that write research papers or sections

What sources report:
- **data-to-paper: Autonomous LLM-driven research from data to human-verifiable research papers.** Ifargan, Hafner, Kern, Alcalay, Kishony. 2024, preprint. arXiv 2404.17605. [verified, 3-vote] LLM agents go from annotated data to a full paper; "information-tracing" chains every result back to the analysis code. Novelty was limited, and human co-piloting was needed for accuracy on harder goals. Uses API models; code is open [unverified: MIT licence, GitHub repo].
- **The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery.** Lu et al. 2024, preprint. arXiv 2408.06292. [verified, 3-vote] Writes full papers from its own experiment logs. "Passes acceptance threshold" is judged only by its own automated reviewer; Limitations section says it can "hallucinate entire results". Not holdable to planted facts.
- **OpenScholar: Synthesizing Scientific Literature with Retrieval-augmented LMs.** Asai et al. 2024. arXiv 2411.14199. [verified, 3-vote] OpenScholar-8B answers science questions with citations from 45M open-access papers. [unverified: it is Llama 3.1 8B fine-tuned, open weights on Hugging Face; experts preferred it to expert answers 51% of the time.] A literature-synthesis tool, not a fact-held generator.
- **LitBench.** Varvarigos, Maatouk, Zhang, Bui, Chen, Tassiulas, Ying. 2026, preprint (cs.DL). arXiv 2603.00051. [verified, 3-vote] Open-weight Llama-3.2-1B-Lit, Llama-3.2-3B-Lit, Llama-3-8B-Lit, trained on domain subgraphs (~12–14k papers, 282–373M tokens each) from an arXiv snapshot. Tasks go up to related-work generation. No realism test, no fixed-fact control.
- **LitFM: A Retrieval Augmented Structure-aware Foundation Model for Citation Graphs.** 2024. arXiv 2409.12177. [verified] Citation-graph retriever + fine-tuned LLM; abstract reports +7.52% average over state of the art on six literature tasks. Abstract gives no size or weight release.
- **Citegeist: Automated Generation of Related Work Analysis on the arXiv Corpus.** Beger, Henneking. 2025, preprint. arXiv 2503.23229. [verified, 3-vote] RAG over arXiv to write related-work sections. On 11 drafts, GPT-4o judge gave 6.90 relevance / 7.55 quality vs 5.78 / 7.27 for the human sections; Gemini rated humans higher. No human or detector realism test.

Suggestion: none of these is a drop-in generator for planted facts. Two parts are worth borrowing: data-to-paper's "every number links to its source" design, and OpenScholar/Citegeist-style retrieval to add **real citations and related-work text**, which is one of our classifier's main cues.

## Q2. Realistic text from structured data with exact numbers

What sources report:
- **Faithfulness in Natural Language Generation: A Systematic Survey.** 2022. arXiv 2203.05227. [verified, secondary] On long data-to-document tasks (Rotowire, MLB), neural systems trail template baselines on fact precision. Plan-then-generate (pick facts as a skeleton, then expand) is the main faithfulness method. Most methods ignore numbers, and sub-word tokenisation makes numerals error-prone. PARENT is the standard table-faithfulness metric.
- **FACTS: Table Summarization via Offline Template Generation with Agentic Workflows.** Yuan, Shabani, Liu. ACL 2026 Findings. arXiv 2510.13920. [verified, 3-vote] An agent writes SQL + Jinja2 templates once; code renders the numbers. Human evaluation still estimated ~92% factual correctness (94% SQL × 98% rendering).
- **ASPIRO: Any-shot Structured Parsing-error-Induced ReprOmpting for Consistent Data-to-Text Generation.** Vejvar, Fujimoto. Findings EMNLP 2023. arXiv 2310.17877. [verified, 3-vote] The LLM writes entity-agnostic templates (slots, not values); code parsing checks trigger re-prompts; 66% average parsing-error reduction on DART vs direct LLM output.

Common pattern across sources: numbers never pass through free generation. They live in data/code, and the model only writes wording. All tests are one sentence to one paragraph long.

Suggestion: ask Haiku/Sonnet to write the 1,000-word paper with `{rag_correct}/{rag_total}` style slots, have code reject any draft containing a raw number that is not a slot, fill slots, then run the existing blind recovery check.

## Q3. Making synthetic text hard to tell from real

What sources report:
- **Computational Turing Test Reveals Systematic Differences Between Human and AI Language.** Pagan, Törnberg, Bail, Hannák, Barrie. 2025, preprint. arXiv 2511.04195. [verified] A BERT classifier still spots calibrated output of nine open-weight LLMs at 70–80% accuracy. **Stylistic examples and context retrieval consistently lowered detectability**; personas and fine-tuning were less reliable. More human-like text kept less of the target meaning (realism vs fidelity trade-off). Instruction-tuned models were less human-like than base models; bigger models did not help. Data is social-media replies, not papers.
- **Language Model Detectors Are Easily Optimized Against.** Nicks, Mitchell, Rafailov, Sharma, Manning, Finn, Ermon. ICLR 2024. [verified, abstract page] RL fine-tuning with a detector's "human-ness" score as reward (KL-constrained): Llama-2 7B, under a day, OpenAI RoBERTa-Large detector AUROC 0.84→0.63, perplexity only 8.7→9.0; evasion transferred to detectors not used in training.
- **Stress-testing Machine Generated Text Detection: Shifting Language Models Writing Style to Fool Detectors.** Pedrotti, Papucci, Ciaccio, Miaschi, Puccetti, Dell'Orletta, Esuli. Findings ACL 2025. arXiv 2505.24523. [verified, 3-vote] DPO on Llama 3.1 8B / Gemma 2 2B with human text preferred (~6–7k pairs). On XSUM news, macro-F1 fell 1.00→0.52 (RoBERTa), 0.99→0.33 (Binoculars). **On arXiv abstracts a fine-tuned RoBERTa only fell 1.00→0.97** and a linguistic-feature SVM 0.96→0.92.
- **Language Models Optimized to Fool Detectors Still Have a Distinct Style (And How to Change It).** Rivera Soto, Chen, Andrews. 2025. arXiv 2505.14608. [verified, 3-vote] After DPO against FastDetectGPT, zero-shot detectors fell to ~35 AUROC, but a few-shot style detector stayed at 96–99. (One checker-refuted summary of this paper's baseline numbers was dropped.)
- [unverified] MASH, arXiv 2601.08564 (multi-stage DPO "humanising" paraphraser); arXiv 2506.12843 (human-looking rewrites became detectable again once classifiers were retrained on them).

Suggestion: our TF-IDF classifier is in-domain and trained, i.e. the strong kind that DPO barely moved on scientific text. Do cheap things first (retrieved real passages as style examples, varied system names, real citations, "we propose" framing), then consider tuning. Always re-train a fresh classifier on held-out folds after any fix.

## Q4. Better template-based generation

What sources report:
- **TempLM: Distilling Language Models into Template-Based Generators.** Zhang, Lee, Li, Shen, Hashimoto. 2022. arXiv 2205.11055. [verified, 3-vote; venue Findings ACL 2023 unverified] Distils an LM into many templates: as faithful as templates, more fluent than earlier template systems; cut BART's out-of-domain unfaithfulness from 83% to 0%. Short E2E/SynthBio outputs only.
- **Neural Pipeline for Zero-Shot Data-to-Text Generation.** Kasner, Dušek. ACL 2022. arXiv 2203.16279. [verified, 3-vote] One hand template per fact, then trained modules order, aggregate and compress (fuse/rephrase) the sentences. Trained on WikiFluent (934k Wikipedia paragraphs, filtered by two-way NLI to 714k). Omissions still occur.
- **Data-to-Text Generation with Iterative Text Editing.** Kasner, Dušek. INLG 2020. arXiv 2011.01694. [verified, 3-vote] Trivial templates, then a keep/delete/add-phrase editor (LaserTagger) fuses them. A claim that this "maximises completeness" was **refuted** 1-2: do not assume every fact survives.
- **RIKER and the Coherent Simulated Universe.** 2025/2026, preprint. arXiv 2601.08847. [verified] Generates documents (leases, field reports, HR records) **with no LLM**: modular templates with randomised style, section order and boilerplate; scoring is deterministic against a ground-truth database. No quantitative realism test.

Suggestion: (a) mine many sentence templates from real RAG papers (TempLM idea, done by an LLM offline, checked by code); (b) template-then-rewrite with a per-draft exact-number check; (c) randomise section order and boilerplate as RIKER does.

## Q5. How strong papers report realism

What sources report:
- **Revisiting Classifier Two-Sample Tests.** Lopez-Paz, Oquab. ICLR 2017. arXiv 1610.06545. [verified] C2ST: train a real-vs-synthetic classifier; held-out accuracy near 50% means hard to tell apart. Simple null distribution gives p-values; the classifier's confident features show *where* the sets differ.
- **Formatting and Surface Feature Confounds in AI Text Detection: A Clever Hans Effect.** Dutta Chowdhury, España-Bonet, van Genabith. EMNLP 2026 Findings. aclanthology.org/2026.findings-emnlp.1051. [verified] 86 content-free surface features (formatting, punctuation, length) reach AUROC 0.964 / 0.956 / 0.995 on RAID / M4 / NYT; document structure alone 0.932 on RAID; length alone only 0.624. These cues do not transfer (0.945 within RAID, 0.28 on M4). Surface features explain up to 69% of detector-score variance. Merging paragraph breaks alone shifts some detectors.
- Pagan et al. (above): authors argue human "is this human?" judgments are blunt and unreliable compared with trained classifiers. [verified]
- [unverified] RAID (ACL 2024, aclanthology 2024.acl-long.674): detectors break under changed decoding or light edits. Binoculars (Hans et al., ICML 2024, arXiv 2401.12070): zero-shot detector. arXiv 2303.16028: pairs a real-vs-synthetic classifier with a topic model to separate topic gaps from style gaps.

Pitfalls the sources name: formatting/structure confounds (above); single-detector evaluation can be gamed (Nicks et al.); zero-shot detectors are weak evidence (Rivera Soto et al.).

Suggestion: report (1) TF-IDF C2ST with p-value, (2) a surface-form-only baseline, (3) the same test with system names/citations masked, (4) one zero-shot detector (e.g. Binoculars on the cluster) as secondary, (5) the top features. This shows how much of AUC 1.0 is cue leakage vs style.

## Q6. Benchmarks that plant facts in realistic documents

What sources report:
- **BABILong: Testing the Limits of LLMs with Long Context Reasoning-in-a-Haystack.** Kuratov et al. NeurIPS 2024 Datasets & Benchmarks. arXiv 2406.10149. [verified] Hides exact bAbI fact sentences between sentences of real PG19 books. Authors admit facts come from a different distribution and fine-tuned models learn tokens that separate them from background; they accept this for scale.
- **SynthDocBench: Controlled Benchmark for Long-Context Visual Document Understanding.** Verma et al. COLM 2026. arXiv 2607.10400. [verified] Ground truth sits in a hidden metadata block; numbers are recomputed by code (>5% mismatch → fixed or dropped, <2% removed); 100 questions reviewed by two authors (κ = 0.81, 96% accepted). No realism test; admits its distributions are tighter than real corpora; samples 40% of layouts uniformly to break spurious correlations.
- **RIKER** (Q4 above): ground truth first, documents rendered from it, deterministic scoring. [verified]
- [unverified] arXiv 2506.02921: needles must be semantically coherent with the haystack or they are easy to spot. arXiv 2601.02023: spread facts across positions rather than one block.

Finding across sources: all check fidelity by code against stored ground truth; **none of the opened sources tests realism with a classifier or humans.** Our C2ST would be a step beyond them.

## Q7. Other relevant points

- Realism vs fidelity trade-off is measured (Pagan et al.): plan for it, and track fact recovery and classifier AUC together on every change. [verified]
- Suggestion: our "real papers propose methods, ours only evaluate" cue is a topic gap, not a style gap. The fix is content: give each synthetic study a small invented method contribution (stored in the JSON, not scored) so the genre matches.
- Suggestion: draw system names, benchmark names and author labels from a large varied pool per corpus; fixed names are a pure surface cue.
- Suggestion: pick real comparison passages in the same genres we generate (workshop papers, posters, data cards), or the classifier learns genre, not "synthetic".
- Searches still missing: synthetic meta-analysis corpora (MetaSyn arXiv 2606.17041 and SciConBench arXiv 2606.11337 were seen in snippets only and reportedly use real literature [unverified]); human studies of fake-vs-real scientific abstracts; LLM-written fake-paper detection in peer review; open-weight base vs instruct models for science-style text.

## Open questions

- Does DPO against our own TF-IDF classifier lower AUC on long papers, and does exact recovery survive?
- How much of AUC 1.0 is cues (names, citations, length, format) rather than writing style?
- Do slot or template-then-rewrite pipelines keep 100% recovery at 1,000+ words with real citations?
