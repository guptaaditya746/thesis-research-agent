# Review: Argilla, answer key, agreement, judge (milestone 3, work package C2)

The review half of the gold standard, ported from `github.com/guptaaditya746/labelling` (README
workflow steps 4–11, `docs/EVALUATION.md`, `guidelines/annotation.md`, `src/labelling/{argilla_io,gold,
screening}.py`, `infra/README.md`) to facts with quotes from the Markdown corpus. C1 builds D per
question (`gold/{screen,extract,triage,pool,draft}.py`); this part puts D's candidate facts in front of
people, turns their answers into the reviewed answer key `key.json`, measures how far the review can be
trusted (`report.json`), and provides and calibrates the LLM judge that scoring uses
(`judge-report.json`). Contracts: `docs/e2e-build-plan.md`, "Gold" and "Judge". Reviewers read
[`guidelines.md`](guidelines.md).

| Module | Does |
|---|---|
| `gold/argilla_io.py` | dataset specs and settings, record content, push (upsert by stable id), pull |
| `gold/review.py` | the `$GOLD` layout, C1's files, the corpus, pulled responses, overlap snapshots |
| `gold/export.py` | decision rule, missing facts anchored with `agent/anchor.py`, rows, `key.json` |
| `gold/agreement.py` | Cohen's kappa, bootstrap over questions, triage miss estimate, `report.json` |
| `gold/screening_check.py` | sample of papers screened not relevant, false-negative rate |
| `gold/judge.py` | `support`, `same_fact`, `same_row`, the cache, the calibration |
| `gold/review_cli.py` | the `gold` subcommands below |

## Where things run

| What | Where |
|---|---|
| Argilla + Elasticsearch + PostgreSQL + Redis | Omen (Docker), `gold/argilla/compose.yaml` |
| `gold` commands, the sub-models behind LiteLLM | Slurm compute node (or any machine with the tunnel) |
| Review in the browser | laptop, through `scripts/omen-tunnels` (service `argilla`) |

### Argilla on Omen

```sh
mkdir -p ~/stacks/argilla && cd ~/stacks/argilla
cp /path/to/thesis-research-agent/gold/argilla/compose.yaml .
cp /path/to/thesis-research-agent/gold/argilla/env.example .env   # set passwords and the API key
docker compose up -d && docker compose logs -f argilla            # wait for "Uvicorn running"
```

About 3–4 GB RAM; most start-up problems come from Elasticsearch (`docker compose logs elasticsearch`).
The server version (v2.8.0) matches the pinned `argilla==2.8.0` SDK.

Tunnel: `scripts/omen-tunnels` lists `argilla` (Omen 6900, laptop 26900, gateway 46900, compute 36900).
Laptop first, then the compute node:

```sh
omen-tunnels laptop start argilla      # browser: http://127.0.0.1:26900
omen-tunnels compute start argilla     # scripts: ARGILLA_API_URL=http://127.0.0.1:36900 (the default)
```

Accounts: log in as the owner from `.env`, then add the second reviewer (role `annotator`, workspace
`thesis`) in the UI, or from Python:

```python
import argilla as rg
client = rg.Argilla(api_url="http://127.0.0.1:36900", api_key="...")
rg.User(username="professor", password="...", role="annotator", client=client).create()
client.workspaces("thesis").add_user("professor")
```

Environment of the `gold` commands: `GOLD` (default `gold-data`), `CORPUS`, `CONCEPTS` (default
`concepts`), `RUNS` (default `runs`), `ARGILLA_API_URL` (default `http://127.0.0.1:36900`),
`ARGILLA_API_KEY`, `ARGILLA_WORKSPACE` (default `thesis`), and for the judge `LITELLM_BASE_URL`,
`LITELLM_MASTER_KEY`. Keys are read when a client or model is made and never logged or written.

## Workflow

| Step | Command | Output |
|---|---|---|
| 1. C1 has built D, triage and the pool | `gold build`, `gold triage`, `gold pool` (C1) | `$GOLD/<qid>/{candidates,pool,triage,screening}.jsonl`, `doc.json` |
| 2. Load the review | `gold push all` | datasets `gold-v1-review`, `-overlap`, `-missing`; `$GOLD/overlap.json` |
| 3. Sample papers screened not relevant (default 5 per question) and load them | `gold screening-sample`, `gold screening-push` | `$GOLD/<qid>/screening.sample.json`; `gold-v1-screening` |
| 4. Review ([guideline](guidelines.md)): you do review, missing and screening; both reviewers do the overlap | Argilla UI | responses |
| 5. Both have finished the overlap, before discussing it | `gold snapshot` | `$GOLD/<qid>/snapshots/overlap-<time>.json` |
| 6. Pull everything (every pull also snapshots a changed overlap) | `gold pull` | `$GOLD/<qid>/review/*.jsonl`, `$GOLD/judge/responses.jsonl` |
| 7. Export the keys; adjudicate the listed disagreements (a third person), pull, export again | `gold export all [--adjudicator NAME]` | `$GOLD/<qid>/key.json`, `export.json` |
| 8. Agreement and what the review missed | `gold agreement` | `$GOLD/<qid>/report.json`, `$GOLD/report.json` |
| 9. After scored runs: sample fact-quote pairs, load them, people answer, pull | `gold judge-sample`, `gold judge-push`, `gold pull` | `$GOLD/judge/sample.jsonl`, `sample.json`; `gold-v1-judge` |
| 10. Calibrate the judge | `gold judge-agreement` | `$GOLD/judge-report.json` |
| One verdict, e.g. to try the prompt | `gold judge '{"s": "p12", "p": "evaluatesOn", "o": "HotpotQA"}' "<quote>"` | JSON verdict |

`push` and the other commands take `<qid>`, a comma-separated list or `all`; pushing again updates the
records in place (stable ids: candidate ids, `missing-<qid>`, `screening-<qid>-<paper>`,
`judge-<hash>`) and keeps people's answers. `export`, `agreement` and `judge-agreement` work on the
pulled files; `--pull` pulls first. The overlap questions are chosen once (seeded, `ceil(0.2 x
questions)`, 3 of 12) and kept in `$GOLD/overlap.json`; their records are only in `-overlap`.

## The answer key

Decision rule per answer (`gold/export.py`): **correct** keeps the candidate fact, with its quote, paper
and row; with a correction `s | p | o` the corrected fact (an empty part keeps the candidate's; row
values equal to the old subject or object follow the fix); a correction that does not parse drops it
and is listed. **Incorrect** drops; **unsure** drops and is listed. Vital when answered vital yes. On
the overlap, people disagree when they differ on keep/drop or keep different facts; the adjudicator's
answer decides (flagged when the adjudicator is one of the two raters); unresolved disagreements stay
out and are listed. A fact both keep is vital only if both said so.

Missing facts (from the missing and screening records) are anchored in their file with
`agent/anchor.py`; anchored ones become key facts (quote = the exact text in the file, vital false,
`candidate_id` null), the rest are listed in `export.json` `rejected` with the anchor's reason
(`not_found`, `partial_number`, `ambiguous`, `unknown_file`, `format`).

Rows: kept facts are grouped into rows of the concept's answer shape (`merge_rows`): one graph row per
(source, predicate, target) of the candidate's row; one table row per value of the concept's first
column, other cells the first value given, list cells the union. An added fact joins the row its
subject or object names, else gets a row built from it. Facts with the same s/p/o in one row are one.

`key.json`: `{qid, concept_sha256, kind, version: "v1", reviewed: true, rows, notes, review}`; facts
`{id, s, p, o, claims: [], origin: "research", paper_id, quote, vital, candidate_id}` (`claims` and
`origin` only so that the rows have the answer schema; the key has no broker claims). Stripping the
gold-only fields (`export.as_answer`) gives a valid answer for `agent.concept.answer_schema_for(concept)`;
export writes no key that does not validate, and none when `doc.json` was built for another concept.
`export.json` lists every decision, disagreements, unsure facts, unreviewed records, added and rejected
lines, merged duplicates and problems; `key.review` counts them (`complete` is false while records are
unreviewed or disagreements unresolved).

## The numbers (`report.json`)

- **Agreement**: Cohen's kappa (`sklearn.metrics.cohen_kappa_score`) between the two most active
  reviewers of the overlap, on the independent round (per record the earliest snapshot in which both had
  answered), for `label`, `keep` (the export's own rule) and `vital` (where both kept), overall and per
  stratum (triaged / sample), with a 95 % percentile bootstrap interval resampling whole questions
  (`scipy.stats.bootstrap`, 2000 resamples, seed 1998; undefined resamples are counted and left out).
- **Triage miss** (labelling `miss_report`, exactly): with N the rest outside the reviewed tiers, n the
  reviewed sample of it and k its kept facts, `estimated_missed = (N - n) k / n` with a 95 % Wilson
  interval (`statsmodels proportion_confint`, method wilson) on k / n scaled by N - n;
  `estimated_recall = tiers_kept / (tiers_kept + k + estimated_missed)`, its interval the Wilson bounds
  in the same ratio.
- **Screening false negatives**: per question, the share of sampled not-relevant papers someone found
  relevant, with a Wilson interval, times the papers screened not relevant; overall the per-question
  estimates summed (bounds summed: conservative) and the pooled rate.

## The judge (`gold/judge.py`, for D and E)

```python
from gold import judge
judge.support({"s": "p12", "p": "evaluatesOn", "o": "HotpotQA"}, quote, context=None)
# {"label": "supports" | "partial" | "no", "rationale", "model", "prompt_sha256", "cached"}
judge.same_fact(run_fact, key_fact, concept)   # {"match": bool, "rationale", ...}
judge.same_row(run_row, key_row, concept)      # {"match": bool, ...}
j = judge.Judge(cache_only=True)               # never calls a model: unseen input -> None (pending)
await j.gather([j.asupport_pair(p, corpus) for p in pairs])   # many, 6 at a time
```

`sub-model-1`/`-2` through `gold/llm.py` (pydantic-ai, structured output, temperature 0, thinking off).
Every answer is cached in `$GOLD/judge-cache.jsonl` under sha256 of the input, the model identity
(pinned name and revision), the prompt hash and the settings, so a rescore costs no model call. Prompts:
`gold/prompts/judge-{support,same-fact,same-row}.txt`. The calibration judges each quote with
`judge.context_for(corpus, file, start, end)` (paper id and 600 characters around the quote); scoring
should do the same (`Judge.support_pair(pairs_line, corpus)` does), so the judge it uses is the one that
was calibrated.

Calibration: `judge-sample` draws 240 pairs (default; `--size`) with a quote from all runs'
`pairs.jsonl`, stratified by condition (equal allocation, population recorded); people answer
supports / partial / no; `judge-agreement` splits the answered pairs into two seeded halves, picks on
the first whether the judge's `partial` counts as yes or no (higher kappa; ties: no), and reports on the
second Cohen's kappa (raw and weighted by condition population, N_h / n_h), the judge's yes-precision
P(person yes | judge yes) and P(person yes | judge no) with Wilson intervals, the 3x3 table and each
person's kappa. People's `supports` is yes, `partial` and `no` are no. Weighted kappa below 0.61: the
report says to report soft scores without the judge, as the labelling repo did.

## Integration notes

- C1's files are read by the contract only. A pool line needs `id` (its candidate's fields are merged
  in); its `stratum` (`triaged` / `sample`) is taken from the line, else from the triage label.
  `pool.strata.json` may give `reviewed_tiers`, `rest`, `sampled`; missing sizes are counted from the
  pool and triage files. A candidate's `row` is the table cells (flat or under `cells`) or the graph
  edge fields.
- `export.merge_rows` implements the draft key's row rule here; once C1's `gold/draft.py` is merged,
  both should call one function so `key.draft.json` and `key.json` group facts the same way.
