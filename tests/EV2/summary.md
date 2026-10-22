# EV2 overnight run summary

Date: 2026-10-22. Branch: `evidence-ev2b`. Slurm job: 7636 on gammaweb07 with three `orch-model` replicas. Full logs and small run artifacts are under this directory; larger live artifacts remain in `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2b/`.

## Run status

| Runbook part | Status | Outcome |
|---|---|---|
| 0.1–0.6 setup | PASS | 1545 Linux tests passed, 1 skipped; orch doctor and model smoke passed. |
| 1–2 corpus copy and checks | PASS | 41 manifests checked; both counterfactual path lists resolved. No synthetic build or variant generation was run on Slurm. |
| 3, 5, 6 engine and baseline lanes | PASS with one corpus-level exception | All requested pilot and `rag-tpl-s1-mixed` engine runs completed. RAG baseline/oracle work completed for the priority corpus; hard-complex RAG oracle exceeded the model context limit. |
| 7 scoring and comparisons | PASS | Score reports and compare-cascade, compare-lexical, and compare-funnel artifacts are refreshed. |
| 8 fidelity review | NOT RUN (USER) | `review-s1.csv` awaits human review. |
| 9–10 live proposal and review | FAIL / NOT RUN (USER) | Freeze refused by blocking critic checks, so there is no final protocol to compare or review. The user must decide any waiver; no waiver was applied. |

## Pilot extraction snapshot

Cascade `all` F1 over the six three-paper `rag-claude-pilot-*` corpora:

| Evidence type | Precision | Recall | F1 |
|---|---:|---:|---:|
| Explicit | 0.9000 | 0.9643 | 0.9310 |
| Paraphrased | 0.9474 | 0.6429 | 0.7660 |
| Distributed | 0.8182 | 0.9643 | 0.8852 |
| Complex | 0.9744 | 0.9500 | 0.9620 |
| Contradictory | 0.9167 | 0.7857 | 0.8462 |
| Mixed | 0.8800 | 0.7857 | 0.8302 |

These are small pilot checks, not the overall study result. The standalone `evaluation_dashboard.html` contains the paper/corpus report selectors and CSV export. `docs/dashboard/README.md` describes generation and scope.

## Known issues and open human work

- `rag-tpl-hard-complex` RAG oracle did not complete: 61,441 input + 4,096 output tokens exceeded the 65,536-token context window.
- The live proposal step exited 2 because critic checks blocked freeze (including `terms_cover_synonyms`); it has no final `protocol.yaml` or protocol comparison.
- The prescribed fidelity sheet and proposal decisions remain human tasks. See `tests/EV2/failures.md` and the runbook's user-only steps.
- A pre-existing frozen corpus file exceeds the packaging size limit: `tests/EV2/corpora/rag-tpl-hard-complex/ground_truth.json` (1,278,474 bytes). New copied run/corpus artifacts were checked to be under 1 MiB.
- The frontend is served by tmux session `ev2-frontend` on compute port 8080; the HTML dashboard/pipeline map by `ev2-dashboard` on 28099. The reverse SSH forwards laptop ports 25173 and 49099, respectively. Both endpoints returned HTTP 200 locally on the compute node. Job 7636 remains running to keep the model stack and services available.
