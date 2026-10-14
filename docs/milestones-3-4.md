# Milestones 3 and 4: what was built, and what still needs the cluster or people

Built on this machine in the end-to-end build of 13–14 Oct 2026 (`docs/e2e-build-plan.md`: decisions,
file contracts, API), merged on `e2e-build`. Everything below is tested against scripted models,
pydantic-ai `FunctionModel`s, fake HTTP servers, an in-memory Argilla and the D1 fixture papers.
**Nothing here has met the real models, the full corpus, the Argilla server or a reviewer yet**, so
there are no results in this file; measured numbers go to `tests/RESULTS.md` and `docs/STATE.md`
once the Slurm session has produced them.

## Milestone 3: gold D, review, answer key, judge

**Done when** (plan): every question has an evidence document D for its picked concept, its facts
reviewed in Argilla into `key.json`, agreement and the screening check reported, and the judge
calibrated against people.

| Part | What is built | Where | Tests |
|---|---|---|---|
| D (C1) | Papers cut at Markdown headings (markdown-it-py) into chunks of up to 40,000 characters; every chunk screened, every relevant chunk extracted into rows of the concept's answer shape with a quote per fact, decoded under a schema derived from the concept; every quote through the broker's claim check, one retry with the reason; rows merged by one rule (`gold/build.py` `merge_rows`); resumable at call granularity (`cache.jsonl`), stable candidate ids, SIGTERM-safe, `gold status` | `gold/{chunks,calls,screen,extract,build,docmd}.py`, `gold/prompts/` | `gold/tests/test_build.py`, `test_chunks.py`, `test_merge.py`, `test_llm.py` |
| Triage, pool, draft key (C1) | Labels answers / context / irrelevant tied to concept and prompt; the stratified, blind, seeded review pool; `key.draft.json` (`v1-draft`, `reviewed: false`) that validates as an answer once the gold-only fields are stripped | `gold/{triage,pool,draft}.py`, `gold build\|triage\|pool\|draft\|status` | `test_build.py`, `test_build_cli.py` |
| Review (C2) | Five Argilla datasets (review, overlap, missing, screening, judge) as specs, upsert by stable record id with a fact digest, pull, overlap snapshots before discussion; the annotation guideline; Argilla v2.8.0 compose file for Omen and the `argilla` tunnel in `scripts/omen-tunnels` | `gold/{argilla_io,review}.py`, `gold/guidelines.md`, `gold/argilla/` | `test_argilla_io.py`, `test_review_prep.py`, `test_review_cli.py` |
| Answer key (C2) | `key.json` (`v1`, `reviewed: true`) by the decision rule (correct / correction / incorrect / unsure, adjudication), kept quotes located again in the frozen file, missing facts anchored as claims are, rows grouped by C1's rule (imported, one implementation), `export.json` with every decision; refuses a key that does not validate or was built on another concept's D | `gold/export.py` | `test_export.py`, `test_build_to_review.py` (C1's real files into C2: the reviewed key groups kept facts exactly as the draft) |
| Agreement and checks (C2) | Cohen's κ (label, keep, vital) on the independent round with a bootstrap over questions, the triage miss estimate (labelling's formula, Wilson), the screening false-negative rate | `gold/{agreement,screening_check}.py` | `test_agreement.py` |
| Judge (C2) | `support`, `same_fact`, `same_row` on the sub-models, async twins on one event loop, cached in `$GOLD/judge-cache.jsonl` by exact input, model pin and settings; `support_pair` gives each quote its calibrated context (paper id and ~600 characters around it); calibration on 240 sampled fact–quote pairs (`judge-sample`, `judge-agreement`: `partial` mapping chosen on one half, κ on the other) | `gold/judge.py`, `gold/prompts/judge-*.txt` | `test_judge.py` |

Commands, files and costs: `gold/README.md`.

### Still needs the cluster

- Proposing and picking the 12 concepts (2.3; `scripts/e2e-concepts.sh`, provisional pick of brief 1,
  `picked_by: provisional-first`; the user may change a pick in the web app before gold is built).
- A gold trial (`gold build qNN --max-papers 20 --out $GOLD-trial`, out of `$GOLD`: gold files there freeze
  the question's provisional pick before the user has seen it): whether vLLM honours the generated extraction schemas,
  real prompt sizes of 40k-character chunks against the 32k sub-model context, the served model name,
  and the real call rate. The README's cost estimate (about 1,000 screening calls and 7–8 M prompt
  tokens per question) is a count of calls and tokens, not a measured time.
- The full builds, triage, pools and draft keys for the 12 questions.
- The judge's first real calls (one verdict from the CLI, then on scored runs).

### Still needs people

- Argilla on Omen (`gold/argilla/compose.yaml`), accounts, and the review itself: every pool record,
  the missing-facts record per question, the screening sample, and the overlap (about 20 % of the
  questions) by two reviewers, snapshotted before they talk; adjudication of the listed disagreements.
- The judge calibration answers (240 pairs from the real batch), after the runs exist.
- Until `key.json` exists for a question, scoring uses `key.draft.json` and marks every score
  `provisional`.

## Milestone 4: 72 runs, scores, report

**Done when** (plan): 12 questions × 2 conditions × 3 repeats are run, scored against the reviewed
keys, and the pre-registered test is reported.

| Part | What is built | Where | Tests |
|---|---|---|---|
| Runs | The batch runner (2.9) with the provisional budget 60 steps / 2M tokens and prompt v2 (1.13, 1.15), the 12 questions in `m4-72.json` and the 4-run `e2e-smoke.json`; `scripts/e2e-batch.sh` runs a manifest into `$RUNS/<name>/` and exports verify, pairs, timeline, graph and PROV; re-execution and replay (2.13); subagents (2.12) built, off | `agent/`, `scripts/e2e-*.sh` | `agent/tests/` |
| Score per run | Rows and facts against the key at strict, normalised and soft levels (one-to-one matching), vital recall, judged precision from the reviewers' rejections, quote support per fact through the calibrated judge, unsourced share, cost with and without attach; `score.json` (schema 2: the plan's keys plus run settings, judge identity, pending decisions, detail) | `scoring/{normalise,match,support,run_score}.py`, `score run` | `scoring/tests/` |
| Batch and report | `score batch` scores the finished attempt of every run key, rescoring when the key or the judge changes; `score report`: per question × condition means, paired differences with BCa intervals over questions, the pre-registered Wilcoxon signed-rank test on support share (two-sided, α = 0.05, not computed below 6 pairs), sensitivity analyses, coverage, completeness and provisional flags; `report.json`, `report.md`, CSV tables | `scoring/{batch,report}.py` | `scoring/tests/test_report.py` (against hand computations and scipy) |
| SPARQL store | Every run's `graph.ttl` in one pyoxigraph store, one named graph per run (`score store`, `score sparql`) | `scoring/store.py` | `scoring/tests/test_store.py` |
| Web app | FastAPI backend (every endpoint of the plan, run stream and job logs over SSE, jobs for concepts, runs and gold, read-only SPARQL, the five provenance queries, a read-only chat agent) and the React frontend (overview, questions and concept cards with pick, runs, run page with answer, claim walk to the highlighted quote, graph, live timeline, claims, provenance and score tabs, compare, results dashboard, gold, jobs, chat); the built frontend is committed in `webapp/web/dist` | `webapp/`, `webapp/web/` | `webapp/tests/`, Vitest in `webapp/web` |

Cluster order after the runs: `scripts/e2e-batch.sh agent/manifests/m4-72.json` (its last line is
`RUNS_ROOT=$RUNS/m4-72`), then, with that root as the runs root of everything after it,
`score batch $RUNS/m4-72 --gold $GOLD --manifest $RUNS/m4-72/manifest.json --corpus $CORPUS`,
`score report $RUNS/m4-72`, `score store $RUNS/m4-72 --path $RUNS/m4-72/.oxigraph`, and the web app
(`RUNS=$RUNS/m4-72 webapp serve`, through an SSH tunnel). One batch root at a time: run ids are
directory names, and the smoke batch has runs of the same names (`q01-claim_on-r1-a1`), so a root
above both would mix them (`score batch` lists the second as `duplicate`, `score store` skips it).
The gold trial goes to its own directory (`gold build qNN --max-papers 20 --out $GOLD-trial`): a file
in `$GOLD/<qid>/` freezes that question's concept pick.

### Still needs the cluster

- The first e2e smoke batch (2.10, `e2e-smoke.json`): whether vLLM/LiteLLM honours the reply and
  attach result schemas, how often the draft becomes the answer, how far 60 steps / 2M tokens go with
  masking; then the user freezes the budget.
- Re-execution and replay on real Landlock runs (`scripts/e2e-replay.sh --reexec`).
- The 72 runs (more than one 48-hour job; cut runs are rerun fresh by the batch runner).
- Subagents only if single-agent runs overflow (C4).

### Still needs people

- The reviewed keys (milestone 3) before scores are final, and the judge calibration before the soft
  level and support share are reported with the judge (before it, and below κ 0.61, `score report` says
  so first and marks the primary test unvalidated; below the bar it leaves the soft outcomes out).
- Freezing the budget after the smoke batch, and confirming or replacing the provisional concept picks.
