# Checking the evidence system on real papers (research notes, 1 Nov 2026)

Legend: **[checked]** = link opened or file listed today. **[recall]** = from memory of the paper, not re-checked today.

## 1. Labelled datasets of real papers

| Dataset | What is labelled | A / B / C | Size | Format, licence | Where (status today) | Effort to adapt |
|---|---|---|---|---|---|---|
| **Yun et al. 2024 (MLHC), "llm-meta-analysis"** | Per (intervention, comparator, outcome) triple: events and group size per arm, or mean/SD per arm. Linked to Evidence Inference prompt ids | A (arm names, values), **B (value → arm → outcome)**, C via computed effect | 120 RCTs, 699 records (183 binary, 516 continuous); 59% have complete numbers | CSV/JSON + PMC text as XML and markdown; Apache-2.0 | github.com/hyesunyun/llm-meta-analysis, `evaluation/data/annotated_rct_dataset.csv` **[checked]** | **Low.** Already the "41 of 120" shape. Text already in markdown |
| **Evidence Inference 1.0/2.0** (Lehman 2019, DeYoung 2020) | Prompt = (I, C, O) + label: significantly increased / decreased / no difference + evidence sentence | A (I/C/O names), B (which result goes with which triple), **C ("does A beat B on O")** | v1 ≈2.4k articles/10k prompts; v2 adds 25% **[recall for counts; +25% checked]** | CSV + PMC txt/xml in repo; MIT | github.com/jayded/evidence-inference, `annotations/` **[checked]**. The ebm-nlp.com download page timed out | **Low.** Labels are direction-only, no numbers |
| **SciREX** (Jain 2020) | Mentions (Method, Metric, Task, Dataset), coref clusters, salient entities, 4-ary (Method, Metric, Task, Dataset) + Score | A, **B (n-ary links)** | 438 full ML papers **[recall]** | JSONL; Apache-2.0 | GitHub tarball, 7.3 MB **[checked]** | Medium. Relations were built partly from PwC leaderboards, so some gold links are not in the text (repo warns of this) |
| **NLP-TDMS / TDMSci** (Hou 2019, 2021) | Paper → (Task, Dataset, Metric, Score) tuples; TDMSci = entity tags | A, B | ≈330 NLP papers **[recall]** | Files in repo, PDFs fetched by script; Apache-2.0 | github.com/IBM/science-result-extractor, archived (read-only) July 2024 **[checked]** | Medium. Need to download PDFs |
| **SciLead** (Şahinuç et al., EMNLP 2024) | Hand-curated (Task, Dataset, Metric, Result) per paper + leaderboards | A, B (part), **C ("which is best")** | 43 papers, 295 tuples, 27 leaderboards **[checked]** | TSV/JSON | ACL Anthology attachment `2024.emnlp-main.453.data.zip` **[checked]** | **Low.** Small. Note: "best result per metric, may not be the same model" so the method→value link is weak |
| **Papers with Code archive** (after July 2025 shutdown) | Leaderboards: paper, model, dataset, metric, value; methods; paper↔code | B, C (rankings, A>B>C chains across papers) | Very large; eval tables ≈138 MB parquet | Parquet; CC-BY-SA-4.0 | huggingface.co/datasets/pwc-archive/evaluation-tables **[checked]**; GitHub `paperswithcode-data` now points there | Medium. Entries crowd-sourced, have errors (SciLead authors say many are incomplete or wrong) |
| **AxCell** (Kardas 2020) | arXiv papers, table cells linked to leaderboard results | B | Small leaderboard file (70 KB xz) **[checked]** | JSON; Apache-2.0 for code, data licence not stated | GitHub release v1.0 **[checked]** | Medium-high (works on LaTeX tables) |
| **SciERC** (Luan 2018) | Entities + relations (USED-FOR, COMPARE, …) in abstracts | A, weak B | 500 abstracts **[recall]** | JSON | not checked | Low use: abstracts only, no values |
| **EBM-NLP** (Nye 2018) | P/I/O spans in RCT abstracts, test set by doctors | A only | 4,993 abstracts **[checked]** | tar.gz in repo; licence not stated | github.com/bepnye/EBM-NLP **[checked]** | Low, but only finds names |
| **SciFact** (Wadden 2020) | Claim + abstract → supports / refutes + rationale | C-like ("do papers agree") | 1.4k claims, 5.2k abstracts **[recall]** | JSONL; CC BY-NC **[recall]** | S3 tarball **[checked]** | Medium. Claims are single-abstract, not cross-paper |
| **ACL-ARC / SciCite / MultiCite** | Citation intent: Uses, Extends ("builds on"), Background… | **C ("which later studies build on X")** | ACL-ARC ≈1.9k citations **[recall]**; SciCite ≈11k **[recall]**; MultiCite 12.6k contexts / 1.2k papers | ACL-ARC, SciCite on AI2 S3 **[checked]**; MultiCite JSON, CC BY-NC 2.0 **[checked]** | Medium. Gold is per citation sentence, not per paper pair |
| **LimGen** (ECML-PKDD 2024) | Paper → its own "Limitations" section | A (limitations) | 4,068 ACL papers | CC BY 4.0; github.com/arbmf/LimGen **[checked]** | Low. Gold = what authors wrote in a Limitations section, good for recall check |
| **ClinicalTrials.gov results** | Posted per-arm numbers, outcome names, linked PMIDs | A, B, C (via distant supervision, §2) | Thousands of trials with results | API v2, public domain | clinicaltrials.gov/api/v2 **[checked]** | Medium (match paper ↔ registry) |
| Trialstreamer / RobotReviewer | Machine-made PICO + RoB, not human gold | none as gold | – | – | trialstreamer.robotreviewer.net does not resolve **[checked]** | Do not use as gold |
| LEADS (2025), CliniFact (2024), CTO (2024) | Registry ↔ publication pairs, claims from registry results | B/C | LEADS data release not found; CliniFact ≈2k claims / 992 trials | – | not verified | Useful as method examples |

No labelled dataset exists for the RAG-factuality topic itself. The closest gold is PwC leaderboard rows for RAG papers on QA sets (NQ, TriviaQA, PopQA…).

## 2. Ways to avoid or shrink hand labelling

1. **Registry as gold (distant supervision).** Compare the system's arm-level numbers from the paper with ClinicalTrials.gov posted results for the same NCT id. Used by CliniFact (claims built from registry results, checked against PubMed). **Pitfall:** registry and paper disagree on their own. Hartung et al. 2014 (Ann Intern Med) found the primary-outcome *value* inconsistent in 20% of trials and the primary-outcome description in 15%. So a "miss" is not always a system error. Score only exact matches on the primary outcome and hand-check every mismatch. That way the noise turns into a small labelling job, not a wrong score.
2. **Leaderboards as gold.** PwC archive or SciLead give (paper, dataset, metric, value). This gives free B and C labels ("which is best", chains). **Pitfall:** crowd errors; "best number per paper" may mix models; SciREX inherited these gaps. Use SciLead (hand-curated) or keep only PwC rows whose value you find word-for-word in the paper.
3. **LLM-as-judge plus a small human sample.** Bavaresco et al. (ACL 2025, JUDGE-BENCH, 20 tasks, 11 models): agreement with humans varies a lot from task to task, so check the judge on your own task first. **Pitfall for this thesis:** the system and the judge use the same model, so they make the same mistakes and the judge goes easy on them. Use the judge only for fuzzy matching (is "ORR" the same as "objective response rate"?), never for the yes/no answer.
4. **Sampling with confidence intervals.** For precision, hand-check a random sample of extracted items. With n=100, a Wilson 95% interval is about ±8–10 points. **Prediction-powered inference** (Angelopoulos et al., Science 2023; PPI++ 2023, `ppi_py`) combines many cheap judge labels with a small human sample. It gives a valid interval that is never wider than the human-only one. This is the cleanest way to report "LLM-judged, human-corrected" numbers.
5. **Perturbation checks on real papers.** Change one number or swap the arm labels in a real paper, then check that the extracted value and the final answer change as expected. This is like the entity-swap knowledge-conflict tests (Longpre et al. 2021; Zhou et al. 2023, context-faithful prompting). **Pitfall:** the model may remember the real paper (arXiv 2404.06283 shows memory leaks into answers). So the test measures faithfulness, not accuracy. It needs no labels and maps cleanly onto A→B→C: an edit to the text should change one item, one link and one answer.
6. **Cross-system agreement.** Compare with a baseline (plain LLM, RAG). Look only at the items where they disagree. A medRxiv two-LLM study found ≈0.94 accuracy where models agreed, but 0.41–0.50 where they disagreed. So agreement is a cheap way to triage, not proof: same-model systems share errors.

## 3. Recommendation (ranked)

**1. Drug topic on Yun et al. 2024 + Evidence Inference (≈1–2 days).** Take the 120 RCTs (markdown already provided). Gold gives arm names and outcome names (A), events/total per arm tied to an (I, C, O) triple (B), and the significance direction from the linked Evidence Inference prompt (C: "does A beat B on O"). Score A, B and C separately on real text with no new labelling.
*Claim:* "On 120 real RCT reports with independent expert labels, extraction / linking / answer accuracy is X / Y / Z, compared with the synthetic scores."

**2. ML topic on SciLead (+ SciREX for names) (≈1–2 days).** 43 papers, 27 hand-checked leaderboards: gold for value finding, (dataset, metric, value) linking, and "which is best" / A>B>C ordering across papers. Run the existing SciREX name check alongside it. Treat the method→value link as soft (see caveat). Optional: add PwC-archive rows for a few RAG QA leaderboards, keeping only values found word-for-word in the paper.
*Claim:* "On real ML papers, cross-paper rankings built from our extracted values match curated leaderboards in N of 27 cases. Errors are traced to extraction vs linking."

**3. Label-free perturbation test + PPI-calibrated precision on the 5 arXiv RAG papers (≈1 day).** Make 3–5 edits per paper (change a value, swap a method name, delete a limitation sentence). Check that the right item, link and answer change. Add a 100-item random precision sample (or LLM judge + PPI) for limitations and builds-on, where no good gold exists.
*Claim:* "On real RAG papers the pipeline is faithful to the text: X% of single edits carry through to the expected item, link and answer, and item precision is P ± CI."

Skip as main tools: Trialstreamer/RobotReviewer (no human gold, site down), raw PwC without filtering, and registry matching as a primary score (20% built-in disagreement). Use registry matching only as a later extension. Builds-on via MultiCite/ACL-ARC is possible but is per citation sentence. It needs mapping work, so keep it for later.

## Sources
- Yun et al. 2024: arxiv.org/abs/2405.01686; github.com/hyesunyun/llm-meta-analysis
- Evidence Inference: github.com/jayded/evidence-inference; DeYoung 2020 arxiv.org/abs/2005.04177
- SciREX: github.com/allenai/SciREX; arxiv.org/abs/2005.00512
- TDMS: github.com/IBM/science-result-extractor
- SciLead: aclanthology.org/2024.emnlp-main.453
- PwC archive: github.com/paperswithcode/paperswithcode-data; huggingface.co/datasets/pwc-archive/evaluation-tables
- AxCell: github.com/paperswithcode/axcell
- EBM-NLP: github.com/bepnye/EBM-NLP; SciFact: github.com/allenai/scifact
- SciCite/ACL-ARC: github.com/allenai/scicite; MultiCite: github.com/allenai/multicite
- LimGen: arxiv.org/abs/2403.15529
- Hartung et al. 2014, Ann Intern Med 160(7):477-83
- Bavaresco et al., arxiv.org/abs/2406.18403 (ACL 2025)
- Angelopoulos et al., arxiv.org/abs/2301.09633; PPI++ arxiv.org/abs/2311.01453
- Zhou et al. 2023 arxiv.org/abs/2303.11315; arxiv.org/abs/2404.06283
- LEADS arxiv.org/abs/2501.16255; CliniFact medRxiv 10.1101/2024.10.08.24315103
