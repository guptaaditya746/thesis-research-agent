# EV2 corpora written here, by Claude subagents

The decision of 21 Oct 2026: synthetic papers are not the thesis's contribution, and the cluster's Qwen3-30B could not write them reliably (EV2 pilot: 0 of 3 families retained, values repeated in the distributed and contradictory levels; `docs/claude-ev2-handoff.md` on `evidence-ev2`). The corpora are therefore built on the laptop and committed. The cluster only reads frozen corpora: it runs the engine, the baselines, the oracles and the scores.

## How

The synth pipeline stays the same:

- the same ground truth, plans and prompts (`statements-v1.txt`, `render-v2.txt`, `blind-v2.txt`);
- the same statement stage and repair loop;
- every deterministic fidelity check;
- the blind re-extraction compared with the private truth.

Only the models change. `modelcall/exchange.py` adds a model answered through files:

- `--model exchange:<name>` writes each call to `<exchange>/<name>/pending/<id>.json`;
- the answerer writes `<exchange>/<name>/replies/<id>.json`;
- the reply is checked against the output schema before the pipeline sees it.

| Role | Model | Who answers |
|---|---|---|
| Writer | `exchange:claude-haiku-5-5` | Claude Haiku subagents, 5 to 10 requests each |
| Blind verifier | `exchange:claude-sonnet-5-5` | Claude Sonnet subagents. They see only the paper, never the plan. |

The writer and the verifier are different models, as `docs/prompt-writing.md` asks.

Every answerer gets the same brief, given below. In short, it plays the model:

- it uses only the request file;
- it opens no other file and runs no checks;
- it follows the request's instructions literally.

Every call, including the rejected attempts and the repairs, is in the build's call cache, committed as `tests/EV2/claude-writer/*-calls.jsonl`. The cache key carries the model name.

Note: an LLM build is refused (exit 2) until `domains/<domain>/trial.json` has passed on the current generator.yaml; for rag run `synth trial --domain rag --verify-model ...` first (D39).

```bash
synth build --name rag-claude-s1 --seed 1 --studies 20 --levels all --renderer llm \
  --model exchange:claude-haiku-5-5 --verify-model exchange:claude-sonnet-5-5 \
  --min-retained 0.9 --concurrency 200 --out <corpora> --cache <cache.jsonl> --exchange <exchange>
```

The build waits on the pending requests. While it runs, subagents answer them in rounds:

1. statements;
2. papers;
3. repairs;
4. blind readings.

## Limits (say these in the thesis)

- **Not an API call.** The writer is a Claude Code subagent, so the record holds the prompts and replies but no sampling settings. The `seed` in a request only distinguishes retries.
- **Not the cluster model.** The writer differs from the models the engine and baselines use on the cluster. This is intended: the papers are an instrument, and the systems under test all still use the same model.
- **Shared model family.** The writer (Haiku) and the verifier (Sonnet) are both Claude models. They are less correlated than two aliases of the same Qwen weights, but they are not independent. The deterministic checks and the human review sheet do not depend on either model.

## Corpora in `tests/EV2/corpora`

| Corpus | Renderer | Studies | Retained | Papers (first attempt) |
|---|---|---|---|---|
| `rag-claude-pilot-*` | Claude writer | 3 | 3/3 | 15/15 (14) |
| `rag-claude-s1-*` | Claude writer | 20 | 20/20 | 100/100 (98) |
| `rag-claude-k1-*` | Claude writer; 2 duplicates, 2 missing, 2 outliers, 2 irrelevant | 20 | 20/20 | 120/120 (118) |
| `rag-claude-small-{paraphrased,distributed}` | Claude writer, seed 2 | 5 | 5/5 | 10/10 (5; all 5 distributed passed on the second attempt) |
| `rag-claude-s1-mixed-cf-S001-contradicts` | Claude writer, counterfactual | 1 paper | passed | 1/1 (1) |
| `rag-tpl-s1-*`, `rag-tpl-k1-*`, `rag-tpl-s1-mixed-cf-S001-contradicts` | template | 20 | 20/20 | all |
| `rag-tpl-hard-*` | template, `--hard`, knobs 6 each | 100 | 100/100 | all |

The re-tries were all `level_distributed`, the distance check between the code definitions and the table. Each
one passed after a single repair.

A human review sheet (all 20 papers of the mixed corpus, 483 rows, 142 of them priority 1: numbers and claims; step 8 of the runbook) is in
`tests/EV2/corpora/rag-claude-s1-mixed/review/`.

One exchange incident: a verifier reply was read while its file was still empty. It was set aside as "not JSON", and
the identical reply was put back unchanged. The exchange now reads a reply only once it has not changed for 2 s.

Not built: step 1.5 (`--no-statements` comparison), dropped by the user on 21 Oct.

Calls:

- `tests/EV2/claude-writer/calls.jsonl`: the pilot, s1 and k1, 378 calls;
- `calls-small.jsonl`: 30 calls;
- `calls-variant.jsonl`: 3 calls.

The build logs (`*.log`) are next to them.

## Answerer brief (given to every subagent)

See `tests/EV2/claude-writer/answerer-brief.md`.
