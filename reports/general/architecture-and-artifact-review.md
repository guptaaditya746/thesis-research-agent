# Artifact, pipeline and service review

## Artifact storage

Keep compact summaries, run indexes, code commits, corpus and plan hashes, failure logs, and manifests in Git. Store complete run folders (including calls, failed and retry siblings) and caches as lossless compressed archives in durable institutional object storage, recording URI, size and SHA-256 with restore and verification instructions. Preserve recorded paths and verify manifests after restoration. No suitable institutional endpoint or access has yet been verified. Git LFS is an alternative with separate storage and bandwidth costs, but is not installed here. Existing large Git blobs remain in history; do not rewrite history or delete data without approval. GitHub documents [repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits) and [Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

## Evaluation correctness risks

- Full SciLead answer-key attribution fails for scilead-05 and scilead-06 because their saved plans declare a metric parameter but have empty measures. The run-time fix supplies the main measure only when one exists. Preserve the original plans and do not infer gold values from the answer key.
- Rank headline uses top-1, while error-split compares a complete ordered gold ranking. Its `synthesis error` labels are therefore not established causal explanations of top-1 errors. Headline reads the first answer line while error-split may select a different line matching the question.
- Historical replay identity and cache keys changed with the plain-text fix. The historical lock test remains failing beyond the three known baseline failures; no compatibility workaround has been verified against a pre-change recorded run.
- SOFC repeated slots (352/1032 frames) may be unfairly evaluated by the current representation. MeasEval's converter supports a scalar subset, not the entire dataset. See converter-independent-review.md.
- JSONL cache locks are thread-local, not cross-process; use separate caches or a single writer. Job state and subprocess exit status need durable recovery across server restarts.

## Service boundaries and Markdown

Start with modular interfaces: an API and durable job coordinator; an evidence worker combining planning, extraction, graph and queries; the existing model gateway plus recorder; and an evaluation worker. Separate paper intake only if it needs independent scaling. Initially run workers as processes in one Slurm allocation, passing versioned job contracts and artifact manifests, not large paper texts over messages. Preserve offline in-process execution and replay with no network calls. Stabilize replay and cache ownership before introducing HTTP boundaries; test worker restart and idempotence. Splitting services will not by itself make GPU inference faster.

Use structured JSON as the canonical evaluation report and render human-readable Markdown on demand; the existing report writer already emits both. Keep source-paper Markdown and offsets, which extraction and provenance depend on. No historical reports or source data should be deleted without approval.
- In the full SciLead runs, all 22 questions in each reasoning row have at least one context-window failure in the stage report and one unresolved link; two questions per row have a non-done evidence line. These are question-level counts. Ranked question `scilead-07` also displays a generic yes/no answer even though ranked rows exist separately and are used by evaluation; the user-facing response does not directly name the requested paper.
