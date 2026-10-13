# scoring: runs against answer keys, and the milestone 4 report

Milestone 4 of `docs/e2e-build-plan.md` ("Scores", "Primary outcome (pre-registered)"). The measures
follow the labelling repo's `docs/EVALUATION.md` (strict / entailed / soft levels, one-to-one credit,
vital recall, judged precision, BCa intervals over questions), adapted to this project: a concept per
question fixes the answer shape, so there are no ambiguous readings to union (AmbigQA scoring is not
needed), and `normalised` replaces `entailed`.

## Commands

```sh
score run    <run> --key $GOLD/<qid>/key.json           # -> <run>/score.json
score batch  <runs_root> --gold $GOLD --manifest agent/manifests/m4-72.json
                                                          # -> <runs_root>/report/scores.jsonl, batch.json
score report <runs_root>                                 # -> <runs_root>/report/report.json, report.md, *.csv
score store  <runs_root> [--path $RUNS/.oxigraph]        # every run's graph.ttl into the SPARQL store
score sparql <query.rq> [--run <run_id>] [--path ...]    # read-only query, {vars, rows} as JSON
```

`run` and `batch` take `--corpus` (default `$CORPUS`: runs `agent verify` and gives the judge each
quote's paper title), `--no-judge` and `--workers N` (parallel judge calls, default 6 = 3 per
sub-model replica). `batch` without `--manifest` scores every run directory under the root and finds
its key by concept hash; `--force` rescores runs whose score.json is current.

Order on the cluster, after the runs: `agent batch` → `score batch` → `score report` (→ `score store`
for the web app's provenance queries).

## Measures

| Measure | Definition |
|---|---|
| **Support share** (primary) | facts whose quote supports them / all answer facts. Each accepted claim's anchored quote (pairs.jsonl) is judged against the fact's s, p, o by `gold.judge.support()`: supports, partial or no; a fact takes the best verdict over its claims. Partial and unsourced count as not supported. Null when the answer has no facts or a verdict is pending |
| Unsourced share | facts citing no accepted claim / all facts. For claim_off after the attach step the attach claims count, and "no source found" is unsourced |
| Fact precision, recall, F1 | at three cumulative levels, one-to-one: **strict** (s, p, o as typed; `2` = `"2"`), **normalised** (NFKC, case, punctuation, spacing, number formats; paper ids aliased: `p012.md` = `p12`, `2025.acl-long.892` = `2025-acl-long-892`), **soft** (also the judge's `same_fact`, asked only for same-subject pairs where one side is left over after the normalised level) |
| Vital recall | matched vital gold facts / vital gold facts (at each level; the top-level number is soft) |
| Judged precision | correct / (correct + wrong), with coverage (correct + wrong) / run facts: correct = matched at the soft level, wrong = equal (normalised) to a fact reviewers rejected, from the key's optional `rejected` list. Null when the key has no such list |
| Row precision, recall, F1 | set F1 over rows (graph answers: edges). A table row matches when every cell the key fills equals the run's after normalisation (lists as sets; **count cells exactly**, no tolerance); a graph row on source, predicate and target. Soft: also the judge's `same_row` for left-over rows sharing a value |
| Cost | from `agent.verify.stats`: steps, model calls, tokens and seconds, with and without the attach step; claim steps and their tokens |

Credit is a maximum matching (`scipy.optimize.linear_sum_assignment`) weighted so that more pairs,
then more vital gold facts, then stricter pairs win; a fact stated twice (same normalised s, p, o) is
one fact. An empty answer scores precision, recall and F1 0 (every attempt counts); its support share
is undefined.

The judge is `gold/judge.py` (package C2), imported lazily (`scoring/judge.py`); tests inject fakes.
It caches every decision in `$GOLD/judge-cache.jsonl` (`--gold` sets `$GOLD`). A failed or missing
judge never stops scoring: its decisions are counted as pending, soft equals normalised, and the
support share stays null until `score batch` runs again with the judge (scores with pending
decisions are rescored automatically then).

## Pre-registered analysis (fixed 13 Oct 2026, before any scored run)

- **Primary outcome:** support share, claim_on vs claim_off (after the attach step).
- **Aggregation:** per question, the mean over its repeats (3 in m4-72); a run without answer facts
  has no support share and is left out of the mean. Questions with a mean in both conditions are paired.
- **Test:** Wilcoxon signed-rank on the paired per-question means, two-sided, α = 0.05:
  `scipy.stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided", method="auto")` (scipy 1.18.1;
  differences rounded to 12 decimals, zeros dropped; exact null distribution up to 50 pairs).
- **Estimate:** mean difference with its 95 % BCa bootstrap interval (`scipy.stats.bootstrap`,
  paired, resampling questions, 2,000 resamples, seed 20261013); effect size the matched-pairs
  rank-biserial correlation (T+ − T−) / (T+ + T−).
- **Too few questions:** with fewer than 6 paired questions the test is reported as not computed:
  even six-of-six same-sign differences are needed for p ≤ 0.05 (2/2⁵ = 0.0625 > α).
- **Sensitivity:** the same test with runs without answer facts counted as support share 0.
- **Secondary outcomes** (intervals, no tests): fact precision, recall and F1 (soft; F1 also strict and
  normalised), row F1, vital recall, judged precision, unsourced share, tokens and time with and
  without the attach step.
- **Draft keys:** scores against `key.draft.json` are provisional; the report says so in its first
  line and they are never reported as results.

## Files

| File | Content |
|---|---|
| `<run>/score.json` | `run_id, qid, condition, seed, temperature, repeat, attempt, kind, exit_status` (submitted, budget, context_full, error, cut, …), `verify_ok` (null without a corpus), `verify_errors, key_version, key_reviewed, key_sha256, key_path, provisional, key_problems`, `rows` {tp, fp, fn, precision, recall, f1} (soft), `rows_by_level` {normalised, soft}, `facts` {strict, normalised, soft: {tp, fp, fn, precision, recall, f1, vital, vital_tp, vital_recall}}, `vital_recall` (soft), `judged_precision` {correct, wrong, precision, coverage}, `support` {facts, with_claims, supports, partial, no, unsourced, pending, support_share, unsourced_share}, `cost` {steps, model_calls, tokens, tokens_without_attach, seconds, seconds_without_attach, claim_steps, claim_step_tokens, attach_tokens, attach_seconds}, `judge` {used, name, models, calls, pending, errors}, `detail` {rows, facts: {pairs, missed, extra, duplicates}, support: per fact {row_id, fact_id, origin, label, claims: [{claim_id, file, label, rationale, model}]}}, `scored_at` |
| `report/scores.jsonl` | one score.json per scored run, by run id |
| `report/batch.json` | every run key (or run) with its state (finished, cut, failed, attach_pending, not_started, no_key, score_failed) and whether it was scored |
| `report/report.json` | `provisional`, `settings`, `runs` (by condition, by exit status, unscored keys), `questions`, `per_question` (means per question × condition), `paired` (per question: claim_on, claim_off, difference per outcome), `summary` (per outcome: each condition's mean and the paired difference, each `{n, mean, low, high, method}`), `primary` (the test above, `sensitivity_empty_as_zero` inside), `secondary` |
| `report/report.md` | the primary test, outcomes by condition with intervals, per-question table, runs by exit status |
| `report/*.csv` | per_run, per_question, paired, summary, exit_status |
| `$RUNS/.oxigraph/` | pyoxigraph store, one named graph `urn:thesis-agent:run:<run_id>` per run |

The answer key format is the plan's (`key.json` / `key.draft.json`). One optional addition is read if
present: `rejected: [{s, p, o, verdict: "wrong", ...}]`, the facts reviewers rejected as wrong, for
judged precision.

## Code

`normalise.py` (comparison keys), `match.py` (rows and facts against the key), `support.py` (quote
verdicts), `judge.py` (the gold.judge adapter), `run_score.py` (score.json), `batch.py`, `report.py`,
`store.py` (SPARQL store), `cli.py`. Tests in `tests/` use the agent test runs (`agent/tests/runs.py`)
and a scripted judge; none needs a model.
