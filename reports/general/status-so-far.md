# General-system run: status and findings

Status as of 4 November 2026: stopped at the section 5.3 USER checkpoint. No evaluation runs have been completed. The user chose to continue past the failed ReadClaim check; the next decision concerns unavailable SOFC tuning examples. No repository code or prompts were changed.

## Failures and limitations

- Offline pytest: **3 failed, 2,336 passed, 1 skipped**. Two effect-score golden tests differ in token counts; one webapp run-group naming assertion differs. Full trace: [offline test log](logs/offline-pytest.log).
- ReadClaim failed twice on the existing Slurm stack: `UnexpectedModelBehavior: Exceeded maximum output retries (1)`. A single-sentence diagnostic showed both model responses repeating the instruction 33 times, reaching the output length limit and leaving incomplete JSON. The cause of repetition is not established. No ReadClaim score is available. See [diagnosis](readclaim-diagnosis.md) and [retry log](logs/readclaim-retry.log).
- The three-paper Docling check fetched LaTeX sources; it did not exercise PDF conversion or validate PDF tables.
- CochraneForest, SOFC-Exp and MeasEval were skipped as runbook inputs because the required releases or assumed JSON layouts are unavailable. The actual downloadable SOFC and MeasEval releases have different layouts.
- SciLead has 12 source papers without arXiv IDs. Its other 31 papers were fetched. A shared-storage stall delayed the fetch, then cleared.
- Setup interruptions, command failures and download retries are preserved in [failures.md](failures.md), including the llm-setup local-change note.

## Dataset and ontology findings

Full observed and required shapes are in [dataset-formats.md](dataset-formats.md). In brief:

| Dataset | Observed data | Status |
| --- | --- | --- |
| [SciLead](https://aclanthology.org/2024.emnlp-main.453/) | JSON: 27 leaderboards and 43 annotated papers | Downloaded; 27 questions, 1,190 answer-key records |
| [SciREX](https://github.com/allenai/SciREX) | JSONL scientific papers, entity clusters and relations | Downloaded; 40-paper corpus; 26 questions, 217 records from source |
| [CochraneForest](https://arxiv.org/abs/2505.06186) | Described by paper; archive layout not verified | Required `release.json` unavailable |
| [SOFC-Exp](https://github.com/boschresearch/sofc-exp_textmining_resources) | Text, frame and token annotations and metadata | Downloaded; requires adaptation to assumed JSON |
| [MeasEval](https://github.com/harperco/MeasEval) | Paragraph text, TSV and BRAT annotations | Downloaded; requires adaptation to assumed JSON |

Other downloaded candidate datasets are PRED, PEQQS, Wiki-Measurements, POLYIE, MuLMS, SciERC, SuperCon and QuinEx. They are not integrated into this runbook. Download hashes are in [dataset-downloads.sha256](dataset-downloads.sha256). Raw releases are stored on the cluster under `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real/downloads/`; they are not included in this branch. SciLead and SciREX are under the adjacent `real/scilead/` and `real/scirex/` directories.

MeSH, QUDT and CS-KG ontology fetches succeeded; their hashes are in [ontology-hashes.json](ontology-hashes.json). The full CS-KG archive was also downloaded and checksum verified; it is stored on the cluster and was not loaded by the ontology fetcher.

## Completed preparation

- Main was fast-forwarded to `1f642eb3`. The llm-setup submodule was set to the main-recorded `b962edd`; pre-existing local changes were saved as `llm-setup-local.diff` and stashed on the cluster.
- Used existing Slurm allocation `8424`, rather than leaving a new model allocation running.
- `pack check rag`, `pack check ml` and the initial estimate passed.
- Six template synthetic corpora were generated, covering two seeds and three levels.
- Held-out splits: SciLead kept 22 questions and held 5; SciREX kept 15 and held 4. The [split files](splits/) and logs are included in this branch.
- The SciREX corpus estimate gives 6–30 model calls under the selected protocol and settings; see [estimate](estimate-scirex.json). This is not a measured runtime.

The branch contains reports, logs, ontology hashes and split files. Dataset archives and generated corpora remain on the cluster; no run folders have been produced yet.
