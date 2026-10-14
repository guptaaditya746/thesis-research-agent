# Evidence-level system: package layout and the files between them (14 Oct 2026)

The supervisor's design (14 Oct): research question → hand-written executable protocol → Python engine with
a library of interchangeable extractors → evidence graph → deterministic synthesis, evaluated on a
synthetic corpus generated from structured ground truth, against an answer-level baseline. Our additions:
the agentic extractor, the agent baseline (our research agent, no protocol), the provenance and replay
lane, locate recall. The extractor interface is [extractor-contract.md](extractor-contract.md).

Three packages, each owned by one builder, talk only through the files below.

| Package | Builds | Reads | Writes |
|---|---|---|---|
| `synth/` | ground truth, papers, fidelity check, controlled variants | its own config | a corpus directory (section 1) |
| `evidence/` | protocol, engine, regex + LLM extractors, cascade, provenance, replay, re-execution, graph, synthesis | `manifest.json` and `papers/` of a corpus, a protocol | a run directory (section 3) |
| `evaluation/` | scoring A/B/C, locate recall, answer-level baseline, agent baseline, agentic extractor, report | run directories, baseline outputs, `ground_truth.json` | `report.json`, `report.md` |

Shared code, written before the split and changed only by agreement: `evidence/contract.py` (the
contract's pydantic models), `evidence/rules.py` (effect direction and answer label, used by both the
engine and the ground-truth generator). Existing code reused: `agent/anchor.py`, `agent/canonical.py`,
`agent/chain.py`, `gold/llm.py`, `gold/chunks.py`, `agent/prov.py`.

**Hard rule:** the engine and both baselines never read `ground_truth.json`, `fidelity.json` or
`corpus.json`; only `manifest.json` and `papers/`. A test enforces it.

## 1. Corpus directory (written by `synth`)

```
<corpus>/
  manifest.json       {corpus_id, papers: [{id, file, sha256}]}       # all a system under test sees
  papers/S001.md …    the papers (UTF-8, LF)
  corpus.json         {corpus_id, seed, generator: {name, version, code_sha256}, renderer: template|llm,
                       level: explicit|paraphrased|distributed|complex|contradictory|mixed,
                       question, papers: [{id, study_id, level}], models: {...} | null}
  ground_truth.json   section 2
  fidelity.json       per paper: {id, ok, checks: [{name, ok, detail}], attempts}
```

**Controlled variants:** one set of studies is rendered once per difficulty level into separate corpora
(`<name>-explicit`, `<name>-paraphrased`, …, plus `<name>-mixed`), so a change in score between corpora
comes from the rendering alone. Paper ids stay the same across the variant corpora of one study set.

## 2. `ground_truth.json`

```json
{
  "corpus_id": "rag-s1-explicit",
  "seed": 1,
  "question": "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?",
  "studies": [{
    "study_id": "S001", "paper": "S001", "level": "explicit",
    "conditions":   [{"id": "S001.c1", "role": "baseline", "label": "closed-book model", "aliases": ["B"]},
                     {"id": "S001.c2", "role": "rag", "label": "retrieval-augmented model", "aliases": ["R"]},
                     {"id": "S001.c3", "role": "other", "label": "...", "aliases": []}],
    "metrics":      [{"id": "S001.k1", "canonical": "factual_accuracy", "name": "answer accuracy",
                      "higher_is_better": true}],
    "measurements": [{"id": "S001.m1", "condition": "S001.c1", "metric": "S001.k1", "value": 0.62,
                      "dataset": "..."}],
    "author_claim": {"id": "S001.a1", "direction": "improves"},
    "effect":       {"direction": "supports", "delta": 0.08, "metric": "S001.k1",
                     "rag": "S001.m2", "baseline": "S001.m1"}
  }],
  "placements": [{"fact": "S001.m1", "role": "value", "paper": "S001", "start": 812, "end": 815,
                  "exact": "62%"}],
  "answer": {"label": "supported", "supporting": ["S001"], "contradicting": [], "neutral": []}
}
```

- `role` of a condition: `rag`, `baseline` or `other` (distractors: ablations, other systems).
- `canonical` metric: `factual_accuracy` or `hallucination_rate` (the two that answer the question,
  `evidence/rules.METRICS`) or `other` (distractors such as latency, BLEU).
- `value` is normalised: accuracies and rates as fractions in [0, 1]; papers may write `62%`, `0.62`,
  `62.0` under a `%` header, or a relative change.
- `effect` and `answer` are computed with `evidence/rules.effect` and `evidence/rules.label`; the effect
  is on the primary metric (the first `factual_accuracy`/`hallucination_rate` metric of the study).
- `placements`: where each fact is rendered, raw character offsets into the paper text as stored
  (`agent/anchor.read_text`), one entry per rendering (a value stated in the abstract and the table has
  two). Roles: `value`, `condition_label`, `metric_label`, `claim`. Facts referenced: measurement,
  condition, metric and claim ids.

## 3. Run directory (written by `evidence`)

```
runs/evidence/<run_id>/
  run.json         {run_id, mode: run|replay|reexec, protocol: {id, sha256}, manifest_sha256,
                    extractors: [extractor_id], outputs: {file: sha256}, cost: {calls, model_calls,
                    input_tokens, output_tokens, seconds}}
  protocol.yaml    copy of the protocol run
  events.jsonl     hash-chained (agent/chain.seal); subtypes: locate, extractor_call, merge, synthesis
  calls/<call_id>.json   one ExtractionResult each
  locate.json      per document and evidence type: strategy, scope given to the extractors
  evidence.jsonl   merged Items (found_by filled), canonical order, one per line
  graph.json       {nodes: [{id, type: document|condition|metric|measurement|author_claim, ...}],
                    edges: [{src, dst, rel}]}       # rel: in_document, condition, metric, supports, contradicts
  answer.json      section 4
```

The record cache is `<cache_dir>/extractor_calls.jsonl` (`gold/llm.JsonlCache`), key
`digest([extractor_id, task_sha256])`, value the full ExtractionResult plus its model-call records.
`evidence replay <run>` uses the cache only (a miss is an error) and must reproduce every output hash in
`run.json`; `evidence reexec <run>` bypasses it and writes a stability report.

## 4. `answer.json` (engine) and the baselines' answer

```json
{
  "system": "evidence-engine",
  "question": "...",
  "label": "supported | refuted | mixed | no_effect | insufficient",
  "counts": {"supporting": 3, "contradicting": 1, "neutral": 0, "undetermined": 1},
  "studies": [{
    "document": "S001",
    "direction": "supports | contradicts | neutral | undetermined",
    "delta": 0.08, "metric": "factual_accuracy",
    "rag":      {"condition": "c-…", "measurement": "m-…", "value": 0.70},
    "baseline": {"condition": "c-…", "measurement": "m-…", "value": 0.62},
    "author_claim": {"item": "a-…", "direction": "improves", "agrees_with_data": true},
    "reason": null
  }],
  "supporting": ["S001"], "contradicting": [], "neutral": [], "undetermined": []
}
```

`undetermined`: the document lacks a usable rag/baseline pair on a question metric; `reason` says why. It
does not count towards the label.

The baselines write the same shape with `system: rag-baseline` or `system: agent-baseline`; their
`studies` entries carry only `document` and `direction` (as stated by the model), plus `answer_text` and,
for the RAG baseline, `retrieved: [{document, start, end, score}]`. So the synthesis score (C) compares
every system the same way.

## 5. Evaluation (`evaluation`)

- **A extraction**, per evidence type and difficulty level: precision, recall, F1 of items against the
  ground-truth facts of the same paper (measurement: value within 0.005; condition: role; metric:
  canonical); span accuracy (the item's `value` span overlaps a placement of the matched fact).
- **B integration**: of the matched measurements, the share linked to the right condition (role) and
  metric (canonical); per study, whether the rag/baseline pair the engine used is the true pair.
- **C synthesis**: per-study direction accuracy (vs `effect.direction`), answer label correct, for the
  engine and both baselines.
- **Locate recall**: share of placements inside the scope the engine gave the extractors (`locate.json`).
- **Cascade contribution**: per extractor, items only it found (`found_by`).
- **Stability**: from a re-execution report.
- **Cost**: from `run.json`.
