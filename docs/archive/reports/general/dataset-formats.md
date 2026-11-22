# Real dataset formats and runbook inputs

Source files are in `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real/`. Original archives are preserved; hashes of additional downloads are in `dataset-downloads.sha256`.

| Dataset | Observed release | Runbook input and status |
| --- | --- | --- |
| SciLead | Authors' data ZIP contains `leaderboards.json` (27 records, keys `Dataset`, `Leaderboard`, `Metric`, `Task`) and `tdm_annotations.json` (43 paper entries; entries have `PaperURL`, `TDMs`). | Files placed under `real/scilead/`; evaluation remains to be run. |
| SciREX | Authors' release `test.jsonl`; first document keys include `doc_id`, `words`, `sentences`, `sections`, `ner`, `coref`, `n_ary_relations`, and `method_subrelations`. | Placed at `real/scirex/test.jsonl`; evaluation remains to be run. |
| CochraneForest | Paper and project page describe plots, questions, studies and conclusions; no accessible release archive or actual file layout verified. | `release.json` with `licence`, `released`, and `plots` containing `id`, `question`, `conclusion`, and `studies` with `id`, `direction`, `text` is required. Missing; skipped. The current converter also enforces its release and licence fields. |
| SOFC-Exp | Original archive contains article text, sentence and token annotations, entity/slot labels, frame annotations and metadata, keyed by article ID. Values are text spans. | Expected `sofc.json` with `papers` entries containing `id`, `text`, `values` (`value`, `unit`, `material`, `measure`) and `experiments` (`id`, `slots`). The archive does not supply that assumed layout; skipped pending an adapter and verification. |
| MeasEval | Original archive contains paragraph text, TSV annotations and BRAT annotations; annotations include spans and relation references. | Expected `measeval.json` with optional `fields` and `papers` entries containing `id`, `text`, `field`, and `quantities` (`value`, `unit`, `entity`). Original release differs; skipped pending an adapter and verification. |

Original SOFC-Exp and MeasEval downloads are preserved in `real/downloads/additional/`. PRED, PEQQS, Wiki-Measurements, POLYIE, MuLMS, SciERC, SuperCon and QuinEx were also downloaded as possible future datasets; the present runbook does not provide verified ingestion for them. No adapters or gold labels were created.

Section 3.2's assumed CochraneForest layout cannot be checked without its release. SOFC-Exp and MeasEval differ from the assumed JSON layout, so their layout verification requires a USER decision. SOFC direction checks cannot be performed without compatible inputs.
