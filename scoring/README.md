# scoring: runs against answer keys, and the milestone 4 report

Milestone 4 of `docs/e2e-build-plan.md` ("Scores", "Primary outcome (pre-registered)"). The measures
follow the labelling repo's `docs/EVALUATION.md` (strict / entailed / soft levels, one-to-one credit,
vital recall, judged precision, BCa intervals over questions), adapted to this project: a concept per
question fixes the answer shape, so there are no ambiguous readings to union (AmbigQA scoring is not
needed), and `normalised` replaces `entailed`.

## Commands

```sh
R=$RUNS/m4-72                                            # the batch root e2e-batch.sh prints (RUNS_ROOT=...)
score run    <run> [--key $GOLD/<qid>/key.json]         # -> <run>/score.json
score batch  $R --gold $GOLD --manifest $R/manifest.json # -> $R/report/scores.jsonl, batch.json
score report $R                                          # -> $R/report/report.json, report.md, *.csv
score store  $R --path $R/.oxigraph                      # every run's graph.ttl into the SPARQL store
score sparql <query.rq> [--run <run_id>] [--path ...]    # read-only query (no SERVICE), {vars, rows} as JSON
```

The runs root of scoring (and of the web app, `RUNS=$R webapp serve`) is one batch root, the
`RUNS_ROOT` `scripts/e2e-batch.sh` prints (docs/e2e-build-plan.md, Environment), never the `$RUNS`
above several: run ids are directory names, and the smoke batch and m4-72 both have
`q01-claim_on-r1-a1`. Under a root holding both, `score batch` without a manifest scores the first
and lists the second as `duplicate`, `score store` skips it, and `score report` lists any two scores of
one run id (`duplicates`), so nothing mixes silently, but the numbers are only clean per batch root.

`run` and `batch` take `--gold` (default `$GOLD`: keys, the judge's cache and calibration), `--corpus`
(default `$CORPUS`: runs `agent verify` and gives the judge each quote's context), `--no-judge` and
`--workers N` (parallel judge calls, default 6 = 3 per sub-model replica). With the judge on, a corpus
is required: the judge is calibrated on quotes with their context, and scores must use the same
input. `run` without `--key` takes the run's question's `key.json`, else `key.draft.json`, from
`--gold` (by run id, else concept hash), as the web app calls it.

`batch --manifest` reads the attempts from the manifest's own `runs_root`, where `agent batch` wrote
them: give it the effective manifest `scripts/e2e-batch.sh` writes, `$RUNS/<name>/manifest.json`
(runs_root `$RUNS/<name>`); a manifest whose runs_root does not exist is an error. The report goes to
`<runs_root>/report/` (which the web app started on that root reads). Without `--manifest` every run
directory below the root (nested roots included) whose id is a batch run key is scored, its key found
by concept hash, a second directory with an id already seen listed as `duplicate`; `--all` adds runs
with other ids (ad hoc runs). `--force` rescores runs whose score.json is current. A run that cannot be
scored is recorded as `score_failed` and the batch goes on.

Order on the cluster, after the runs: `scripts/e2e-batch.sh` (agent batch, verify, pairs, graph) →
`score batch` → `score report` (→ `score store` for the web app's provenance queries).

## Measures

| Measure | Definition |
|---|---|
| **Support share** (primary) | facts with a supporting quote / all answer facts. Each accepted claim's anchored quote (pairs.jsonl) is judged against the fact's s, p, o by gold.judge (`support_pair`, with the context the judge was calibrated on: paper id and text around the quote): supports, partial or no. A fact takes the best verdict over its claims. `partial` counts as supporting when the judge's calibration says so (`$GOLD/judge-report.json` `calibration.partial_counts_as`, chosen on half of the calibration sample), else not; unsourced never counts. Null when the answer has no facts or a verdict is pending |
| Support share, other mapping / first claim | sensitivity analyses: `partial` the other way; each fact judged by its first cited claim alone (claim_on facts may cite several claims, claim_off facts at most one after attach) |
| Claims per sourced fact | mean number of accepted claims a sourced fact cites |
| Unsourced share | facts citing no accepted claim / all facts. For claim_off after the attach step the attach claims count, and "no source found" is unsourced |
| Fact precision, recall, F1 | at three cumulative levels, one-to-one: **strict** (s, p, o as typed; `2` = `"2"`), **normalised** (NFKC, case, punctuation, spacing, number formats; letters keep their combining marks; `+` and `#` kept; paper ids aliased: `p012.md` = `p12`, `2025.acl-long.892` = `2025-acl-long-892`), **soft** (also the judge's `same_fact`, asked only for same-subject pairs where one side is left over after the normalised level) |
| Vital recall | matched vital gold facts / vital gold facts (at each level; the top-level number is soft) |
| Judged precision | correct / (correct + wrong), with coverage (correct + wrong) / run facts: correct = matched at the soft level, wrong = equal (normalised) to a fact reviewers rejected as wrong: `$GOLD/<qid>/export.json` decisions answered `incorrect` (also after adjudication), s/p/o from candidates.jsonl or pool.jsonl. Null without an export (draft keys) |
| Row precision, recall, F1 | set F1 over rows (graph answers: edges). A table row matches when every cell the key fills equals the run's after normalisation (lists as sets; **count cells exactly**, no tolerance); a graph row on source, predicate and target. Soft: also the judge's `same_row` for left-over rows sharing a value |
| Cost | from `agent.verify.stats`: steps, model calls, tokens and seconds, with and without the attach step; claim steps and their tokens. `seconds` is active time (research span + attach span), so a queue wait before a later job's attach step does not count; `wall_seconds` is the whole span |

Credit is a maximum matching (`scipy.optimize.linear_sum_assignment`) weighted so that more pairs,
then more vital gold facts, then stricter pairs win; a fact stated twice (same normalised s, p, o) is
one fact. An empty answer scores precision, recall and F1 0 (every attempt counts); its support share
is undefined.

The judge is `gold/judge.py` (package C2), imported lazily (`scoring/judge.py`); tests inject fakes.
Scoring awaits its async methods (`asupport_pair`, `asame_fact`, `asame_row`) on one event loop, at
most `--workers` at a time: the judge's HTTP clients must not be shared between event loops. It caches
every decision in `$GOLD/judge-cache.jsonl`. A failed or missing judge never stops scoring and never
drops a run: its decisions are counted as **pending** (`score.json` `pending`: support, same_fact,
same_row). Pending support verdicts leave the run's support share null; pending soft decisions make
the soft numbers a lower bound, so the report leaves them out of the soft means (and says how many
runs fed each mean). `score batch` rescores a run when its score.json is from another scoring version
or key, was not verified and a corpus is now given, or (with a judge at hand) was made without the
judge, by another judge model or prompt, with another context mode or calibration, or has decisions
pending; the judge's cache makes that free for decisions it has seen. Errors are recorded without HTTP
bodies or anything key-like.

The judge's calibration (`$GOLD/judge-report.json`, `gold judge-agreement`) is recorded per run
(`support.calibration`: partial mapping, `state` passed / failed / none, `use_judge`, the tested kappa
and the bar). The report's primary test is the pre-registered result only when every run's judge
passed (`primary.judge_validated`); otherwise report.md and the web app say first that it is not
calibrated yet or failed, and a judge that failed (kappa below 0.61) decides no soft match either:
those runs' soft outcomes are left out, as pending ones are (strict and normalised stand).

## Pre-registered analysis (fixed 13 Oct 2026, before any scored run)

- **Primary outcome:** support share, claim_on vs claim_off (after the attach step), with the judge's
  calibrated input (context) and partial mapping.
- **Aggregation:** per question, the mean over its repeats (3 in m4-72); a run without answer facts
  has no support share and is left out of the mean. Questions with a mean in both conditions are paired.
  Coverage (scored runs with answer facts / scored runs, and planned runs not scored) is reported per
  condition beside it.
- **Test:** Wilcoxon signed-rank on the paired per-question means, two-sided, α = 0.05:
  `scipy.stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided", method="auto")` (scipy 1.18.1;
  differences rounded to 12 decimals, zeros dropped; exact null distribution up to 50 pairs).
- **Estimate:** mean difference with its 95 % BCa bootstrap interval (`scipy.stats.bootstrap`,
  paired, resampling questions, 2,000 resamples, seed 20261013); effect size the matched-pairs
  rank-biserial correlation (T+ − T−) / (T+ + T−).
- **Too few questions:** with fewer than 6 paired questions the test is reported as not computed:
  even six-of-six same-sign differences are needed for p ≤ 0.05 (2/2⁵ = 0.0625 > α).
- **Pending verdicts:** while any scored run has a pending support verdict the test is reported as
  not computed, with the runs listed; it is never run on a subset of the repeats.
- **Sensitivity:** the same test (1) with runs without answer facts counted as support share 0, (2)
  with `partial` under the other mapping, (3) with each fact judged by its first cited claim only.
- **Secondary outcomes** (intervals, no tests): fact precision, recall and F1 (soft; F1 also strict and
  normalised), row F1 (soft and normalised), vital recall, judged precision, unsourced share, claims
  per sourced fact, tokens and time with and without the attach step.
- **Draft keys:** scores against `key.draft.json` are provisional; the report says so in its first
  line and they are never reported as results. So are scores against a `key.json` whose review is not
  finished (`review.complete` false: `gold export` writes one after every pull).
- **Judge not validated:** with the judge not calibrated yet, or below κ 0.61, the test is shown but
  marked unvalidated (STATE.md, Judge: the support share is then an unvalidated secondary number).

## Files

| File | Content |
|---|---|
| `<run>/score.json` | `schema_version` (3), `run_id, qid, condition, seed, temperature, repeat, attempt, kind, exit_status` (submitted, budget, context_full, error, cut, …), `answer_from` (final, draft, none; null for older runs), `verify_ok` (null without a corpus), `verify_errors, key_version, key_reviewed, key_complete, key_sha256, key_path, provisional, key_problems`, `rows` {tp, fp, fn, precision, recall, f1, asked, pending} (soft), `rows_by_level` {normalised, soft}, `facts` {strict, normalised, soft: {tp, fp, fn, precision, recall, f1, vital, vital_tp, vital_recall; soft also asked, pending}}, `vital_recall` (soft), `judged_precision` {correct, wrong, precision, coverage, source}, `support` {facts, with_claims, supports, partial, no, unsourced, pending, partial_counts_as, support_share, support_share_partial_no, support_share_partial_yes, support_share_first_claim, claims_per_fact, unsourced_share, context (calibrated / none), calibration {partial_counts_as, source, sha256, state, use_judge, kappa, bar}}, `pending` {support, same_fact, same_row}, `cost` {steps, model_calls, tokens, tokens_without_attach, seconds, seconds_without_attach, wall_seconds, claim_steps, claim_step_tokens, attach_tokens, attach_seconds}, `run_settings` {budget, temperature, prompt_version, prompt_sha256, model, corpus_manifest_sha256, git_commit, loop, spawn, sandbox_mode, command_limits, attach}, `judge` (this run's calls) {used, name, identity {name, model, prompts}, models, prompt_sha256, calls, cached, pending, errors}, `scorer` {version, git_commit}, `detail` {rows, facts: {pairs, missed, extra, duplicates}, support: per fact {row_id, fact_id, origin, label, first_claim_label, claims: [{claim_id, file, label, rationale, model, prompt_sha256, cached}]}}, `scored_at` |
| `report/scores.jsonl` | one score.json per scored run, by run id |
| `report/batch.json` | `runs_root`, `attempts_root`, every run key (or run) with its state (finished, cut, failed, attach_pending, not_started, not_a_batch_run, duplicate, no_key, score_failed), `run_dir` and whether it was scored, `key_problems` (key files that did not parse) |
| `report/report.json` | `provisional`, `complete`, `completeness` (pending support / soft runs, unjudged, unverified and verify-failed runs, runs with key problems, judge context, partial mapping, judge calibration and key state counts, `settings_differ`: prompt and attach within each condition), `judge` (calibration state, validated, kappa, bar), `duplicates`, `settings`, `inputs` (sha256 of scores.jsonl and batch.json, scorer and report commits, key hashes per question, judge models, prompt hashes and identities), `runs` (by condition, exit status, answer source, unscored keys), `coverage`, `questions`, `per_question` (means per question × condition, with runs, answered, primary_runs, pending_runs), `paired`, `summary` (per outcome: each condition's mean `{n, mean, low, high, method, runs, runs_without_value}` and the paired difference), `primary` (the test above; `sensitivity_empty_as_zero`, `sensitivity_other_mapping`, `sensitivity_first_claim` inside), `secondary` |
| `report/report.md` | warnings first (provisional, judge not calibrated or failed, duplicates, incomplete, unverified, key problems, differing settings), the primary test with coverage and sensitivity analyses, outcomes by condition with intervals, per-question table, runs by exit status and answer source |
| `report/*.csv` | per_run, per_question, paired, summary, exit_status |
| `<runs_root>/.oxigraph/` | pyoxigraph store (`score store`), one named graph `urn:thesis-agent:run:<run_id>` per run |

The answer key format is the plan's (`key.json` / `key.draft.json`); judged precision reads the review
export beside it (`export.json`, C2) and the candidates' s/p/o (`candidates.jsonl` or `pool.jsonl`).

## Code

`normalise.py` (comparison keys; the `regex` module for Unicode letter and mark classes), `match.py`
(rows and facts against the key), `support.py` (quote verdicts, partial mapping), `judge.py` (the
gold.judge adapter: one event loop, per-run forks), `run_score.py` (score.json), `batch.py`,
`report.py`, `store.py` (SPARQL store), `cli.py`. Tests in `tests/` use the agent test runs
(`agent/tests/runs.py`), a rule-based judge and one shaped like C2's (async methods, prompt hashes);
none needs a model.
