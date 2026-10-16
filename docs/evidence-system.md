# Evidence-level system: interfaces and extractor contract

The file formats and the extractor interface of the evidence-level system (`evidence/`, `synth/`,
`evaluation/`). Two documents of 14 Oct 2026, merged here verbatim: **Part A** was
`docs/evidence-interfaces.md` (packages and the files between them), **Part B** was
`docs/extractor-contract.md` (the interface every extractor implements). Section numbers are kept with a
prefix, so "interfaces section 3" is now **A3** and "contract §10" is **B10**; only cross-references and
heading prefixes were changed. Current state and plan: [`STATE.md`](STATE.md).

Attribution: the pipeline (question → hand-written protocol → engine with interchangeable extractors →
evidence graph → deterministic synthesis, synthetic benchmark with scores A/B/C, answer-level baseline) is
the supervisor's design (14 Oct). The concrete formats, the contract's details (spans, coverage, cache,
replay, re-execution, cascade) and everything listed as "our additions" in `STATE.md` are ours.

# Part A. Evidence-level system: package layout and the files between them (14 Oct 2026)

The supervisor's design (14 Oct): research question → hand-written executable protocol → Python engine with
a library of interchangeable extractors → evidence graph → deterministic synthesis, evaluated on a
synthetic corpus generated from structured ground truth, against an answer-level baseline. Our additions:
the agentic extractor, the agent baseline (our research agent, no protocol), the provenance and replay
lane, locate recall. The extractor interface is Part B.

Three packages, each owned by one builder, talk only through the files below.

| Package | Builds | Reads | Writes |
|---|---|---|---|
| `synth/` | ground truth, papers, fidelity check, controlled variants | its own config | a corpus directory (A1) |
| `evidence/` | protocol, engine, regex + LLM extractors, cascade, provenance, replay, re-execution, graph, synthesis | `manifest.json` and `papers/` of a corpus, a protocol | a run directory (A3) |
| `evaluation/` | scoring A/B/C, locate recall, answer-level baseline, agent baseline, agentic extractor, report | run directories, baseline outputs, `ground_truth.json` | `report.json`, `report.md` |

Shared code, written before the split and changed only by agreement: `evidence/contract.py` (the
contract's pydantic models), `evidence/rules.py` (effect direction and answer label, used by both the
engine and the ground-truth generator). Existing code reused: `agent/anchor.py`, `agent/canonical.py`,
`agent/chain.py`, `gold/llm.py`, `gold/chunks.py`, `agent/prov.py`.

**Hard rule:** the engine and both baselines never read `ground_truth.json`, `fidelity.json` or
`corpus.json`; only `manifest.json` and `papers/`. A test enforces it.

## A1. Corpus directory (written by `synth`)

```
<corpus>/
  manifest.json       {corpus_id, papers: [{id, file, sha256}]}       # all a system under test sees
  papers/S001.md …    the papers (UTF-8, LF)
  corpus.json         {corpus_id, seed, generator: {name, version, code_sha256}, renderer: template|llm,
                       level: explicit|paraphrased|distributed|complex|contradictory|mixed,
                       question, papers: [{id, study_id, level}], models: {...} | null}
  ground_truth.json   A2
  fidelity.json       per paper: {id, ok, checks: [{name, ok, detail}], attempts}
```

**Controlled variants:** one set of studies is rendered once per difficulty level into separate corpora
(`<name>-explicit`, `<name>-paraphrased`, …, plus `<name>-mixed`), so a change in score between corpora
comes from the rendering alone. Paper ids stay the same across the variant corpora of one study set.

## A2. `ground_truth.json`

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

## A3. Run directory (written by `evidence`)

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
  answer.json      A4
```

The record cache is `<cache_dir>/extractor_calls.jsonl` (`gold/llm.JsonlCache`), key
`digest([extractor_id, task_sha256])`, value the full ExtractionResult plus its model-call records.
`evidence replay <run>` uses the cache only (a miss is an error) and must reproduce every output hash in
`run.json`; `evidence reexec <run>` bypasses it and writes a stability report.

## A4. `answer.json` (engine) and the baselines' answer

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

## A5. Evaluation (`evaluation`)

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

## A6. As built (14 Oct): where the code goes beyond this page

- **Corpus:** `corpus_id` is derived from the papers' contents, so it reveals no level; `decoys.json` lists
  the contradictory level's wrong values (not placements). A study failing fidelity at any level is left out
  of every corpus of its set, so the variants keep the same paper ids (`synth/README.md`).
- **Run directory:** `run.json` also holds `extractor_specs`, `chain_head` and the run `settings` (corpus,
  cache, extractor selection, model, imports) so replay and re-execution can repeat the run; `outputs` covers
  every file except `run.json` and `events.jsonl` (timestamps), whose head is `chain_head`. Replay and
  re-execution write a new sibling run directory. Extra event fields live in `custom_metadata`
  (`task_sha256`, `output_sha256`, `model_calls`, `attempt`, `position`); a retried call is a new attempt and
  never overwrites the record an earlier run replays from.
- **Protocol:** `bounds` per evidence type (question-metric values must be fractions in [0, 1]) and
  `synthesis.pairing: same_dataset_table_first` (rag and baseline on the same dataset, a table cell before
  prose, then document order).
- **Agentic extractor:** registered lazily as `agentic`; `evidence/protocols/rag-factuality-agentic.yaml` puts
  it last in every cascade. A cited claim must belong to its row and field, and a value claim's quote must
  hold the cell's number.
- **Baselines:** may open only `manifest.json` and files directly in `papers/`. The retrieve-then-answer
  baseline takes the top 2 BM25 passages of every paper by default (`--retrieval global` for the plain top-k
  over the corpus); the report shows `answered` and `accuracy_answered` next to direction accuracy.
- **Scoring:** items are matched to facts one to one per paper and evidence type (Hungarian assignment); the
  rules are in the `evaluation/score.py` docstring.

# Part B. Extractor contract (draft, 14 Oct 2026)

The supervisor's design (14 Oct) has a library of reusable evidence extractors behind a common interface,
with interchangeable implementations ("regular expressions, specialized models, LLMs, or other methods").
This page fixes that interface: what an extractor receives, what it must return, what it records, and how
a run is made to give the same data every time. It covers four kinds of extractor: **regex**, **model**,
**single-call LLM** and **agentic LLM** (our research agent as one implementation, decided 14 Oct).

## B1. Principles

1. **One contract for every kind.** The engine cannot tell which kind of extractor produced an item.
2. **Every item has a checked source span.** No item enters the evidence graph without a passage that is
   found in the document, as the claim broker checks quotes now.
3. **Absence is recorded.** "Searched this part, found nothing" is provenance too; without it, *missed* and
   *not there* look the same.
4. **Replay is exact.** Every call is recorded and cached; a replay rebuilds the evidence from the records
   and gives the same data, bit for bit, for every kind of extractor. All reported results come from replay.
5. **Re-execution is measured.** Running an extractor again from scratch is a stability test: exact for
   regex, near-exact for LLMs, variable for agents. Its differences are reported, never hidden.
6. **A change is a new version.** Any change to code, patterns, prompt, model or schema changes the
   extractor's id, so old records are never reused for new behaviour.
7. **Quality is measured per version** on the synthetic benchmark, per difficulty level.

## B2. Terms

| Term | Meaning |
|---|---|
| Evidence type | A kind of evidence the protocol asks for (`condition`, `metric`, `measurement`, `author_claim`), with a typed field schema |
| Extractor | A component that finds items of one or more evidence types in a document |
| Task | One request to an extractor: one evidence type, one document, a scope, optional context |
| Call | One execution of a task by an extractor; one provenance event |
| Item | One piece of evidence: typed fields plus one or more source spans |
| Span | A checked passage: file, offsets, exact text, prefix, suffix, file hash (`agent/anchor.py` `Selector`) |
| Coverage | What a call examined, and what it found in each part |

## B3. Identity: `ExtractorSpec`

```yaml
name: reported_result            # stable, a-z0-9_
version: 3                       # bumped by hand on any behaviour change
kind: regex | model | llm | agent
evidence_types: [measurement]
code_sha256: …                   # hash of the extractor's source files
config: { … }                    # kind-specific, B9
config_sha256: …                 # canonical hash of config (agent/canonical.py)
determinism: exact | near_exact | variable
```

`extractor_id = name@version#sha256(code_sha256, config_sha256)[:12]`. Because the id contains both hashes, a
changed prompt or pattern cannot hit the old cache even if the version number was not bumped; the engine
warns when the hashes change but the version did not.

## B4. Input: `ExtractionTask`

```yaml
protocol: { id: rag-factuality, sha256: … }
evidence_type: measurement
field_schema_sha256: …           # the evidence type's JSON schema, from the protocol
document: { id: S07, file: S07.md, sha256: … }
scope:                           # what the extractor may look at
  kind: document | sections | ranges
  ranges: [[0, 18422], …]        # character offsets, when not the whole document
context:                         # items from earlier phases the extractor may use
  - item_id: c-1f3a…             # e.g. the paper's conditions, given to the result extractor
budget: { steps: 30, tokens: 200000 }   # agentic extractors only
```

`task_sha256` is the canonical hash of the task. The extractor receives nothing else: no ground truth, no
other extractor's output except the declared context, no network except the LiteLLM gateway.

## B5. Output: `ExtractionResult`

```yaml
call_id: …                       # assigned by the engine
extractor_id: reported_result@3#9c41e2…
task_sha256: …
status: ok | partial | error     # partial: some items kept, some parts failed
error: null | { reason: …, detail: … }
items: [ … ]                     # canonical order: by first span start, then evidence type
rejected: [ … ]                  # items that failed a check, with the reason (never silently dropped)
coverage: [ … ]
model_calls: [ … ]               # ids of the recorded model calls inside this call (LLM, agent)
```

### Item

```yaml
item_id: m-7b20…                 # sha256(evidence_type, fields, spans' file/start/end)[:16]: same item, same id
evidence_type: measurement
fields: { condition: c-1f3a…, metric: k-02c9…, value: 0.82 }   # validated against the field schema
spans:                           # one or more; each has a role
  - role: value                  # where the number is
    selector: { file: S07.md, start: 18422, end: 18426, exact: "0.82", prefix: "…| R | ", suffix: " |…", sha256: … }
  - role: condition_label        # where "R" is defined as the retrieval-augmented variant
    selector: { file: S07.md, start: 6120, end: 6188, exact: "its retrieval-augmented variant (R)", … }
links: { condition: c-1f3a…, metric: k-02c9… }   # references to other items by item_id
confidence: null | 0.0–1.0       # optional; never used by synthesis
```

Several spans per item are what make **distributed evidence** traceable: the value is in a table, the
meaning of its column is in the method section, and the item points to both. Integration errors (a value
attached to the wrong condition) become visible in the spans and links.

### Rejected item

The item as proposed, plus `reason`: `empty_quote`, `not_found`, `ambiguous`, `partial_number` (from
`agent/anchor.py`), `schema` (fields fail the schema), `out_of_scope` (span outside the task's scope),
`dangling_link` (a link to an unknown item).

### Coverage

One entry per part of the scope the extractor examined:

```yaml
- range: [5200, 9800]            # or a section heading path
  status: found | none | skipped | error
  found: 2                       # items from this part
  reason: null                   # for skipped / error
```

An agentic extractor's coverage is what it actually read (from its commands), so a passage it never opened
is visible as not examined.

## B6. Rules

| # | Rule |
|---|---|
| R1 | Every item has at least one span; every span passes `anchor.find` against the document text whose sha256 is in the task. A failing item goes to `rejected` with its reason. |
| R2 | Fields validate against the evidence type's schema; links point to items in the task's context or in this result. |
| R3 | Spans lie inside the task's scope. |
| R4 | The extractor reads only the document, the declared context and its own configuration. |
| R5 | No randomness without a recorded seed; no clock in outputs; temperature 0 for single-call LLMs. |
| R6 | Failure is a status, not a lost call: what was found before the failure is kept (`partial`). |
| R7 | Output is canonical: items sorted, JSON canonicalised (`agent/canonical.py`), so the same result hashes the same. |
| R8 | The extractor writes no files; the engine records everything (B7). |

## B7. Provenance: one event per call

Each call appends one record to the run's hash-chained `events.jsonl` (the broker's chain, PROV-AGENT
fields):

```yaml
subtype: extractor_call
task_id: <call_id>
used: [document sha256, protocol sha256, context item ids]
generated: [item ids]
agent_id: <extractor_id>
task_sha256: …
output_sha256: …                 # canonical hash of the ExtractionResult
status: ok | partial | error
model_calls: [<task_id of each ai_model_invocation record>]   # LLM and agent calls inside
started_at / ended_at
prev_hash / hash
```

In the PROV-O export: the call is a `prov:Activity` that `used` the document and the protocol and
`wasAssociatedWith` the extractor (a `prov:SoftwareAgent` with its version and hashes); each item is a
`prov:Entity` that `wasGeneratedBy` the call and `wasDerivedFrom` its passages. The answer `wasDerivedFrom`
the items it counted, so a number in the answer walks back to the table cell it came from.

## B8. Cache, replay and re-execution

- **Cache key** = `sha256(extractor_id, task_sha256)`. The cache stores the full `ExtractionResult` and the
  records of every model call inside it (request and response; for an agent its whole trajectory). It is
  the `JsonlCache` of `gold/llm.py`, append-only.
- **Normal run:** a cache hit returns the stored result; a miss runs the extractor and stores the result.
- **Replay** (`engine replay <run>`): cache only. A miss is an error ("not recorded"), never a new call. The
  run's evidence, graph and answer are rebuilt and must hash the same as recorded. This is what "every
  time we run the provenance we get the same data" means, and it holds for every kind of extractor.
- **Re-execution** (`engine reexec <run> [--extractor X]`): bypass the cache, run again, and compare with the
  record per call: `identical`, `same items, different spans`, `items added`, `items missing`,
  `fields differ`. The report is a measurement of stability per extractor.

| Kind | Determinism | Re-execution expected |
|---|---|---|
| regex | exact | identical; a test enforces it |
| model | exact (fixed weights hash, CPU) | identical |
| single-call LLM | near-exact (temperature 0, seed, pinned model revision, schema-constrained decoding) | mostly identical; vLLM batching can change a token, so differences are counted |
| agentic LLM | variable (seed and budget recorded, but the path can differ) | measured: how much of the evidence is stable across reruns |

## B9. Kind-specific configuration

| Kind | `config` holds |
|---|---|
| regex | patterns with flags, the mapping from groups to fields, value normalisers (number formats, percent → fraction) |
| model | model name and weights sha256, thresholds, input window |
| llm | model alias and served revision, `prompt_sha256` (instructions + output schema, `gold/llm.py`), temperature 0, seed, max_tokens, decoding = JSON schema, chunking settings (`gold/chunks.py`), quote-retry rule (one retry with the reason, as `gold/extract.py`) |
| agent | model alias and revision, prompt version and hash, allowed commands, the `claim` command (its accepted claims become items), budget, seed, sandbox mode; its trajectory is part of the record |

## B10. Several extractors for one evidence type

The protocol lists extractors per evidence type in order (a cascade), for example regex, then single-call
LLM, then agent for what is still missing. The engine merges their items: two items of one type with equal
normalised fields are one item that keeps all spans and a `found_by` list. The report gives each
extractor's **marginal contribution** (items only it found) and what none of them found, measured against
the synthetic ground truth.

## B11. Benchmark record per version

`extractors/<name>/<version>/benchmark.json`, made on a synthetic corpus (its id and seed recorded):

- per difficulty level (explicit, paraphrased, distributed, complex, contradictory): precision, recall, F1;
- span accuracy: the span contains the value, and the role spans point where the ground truth's rendering
  plan placed the fact;
- association accuracy: the item links to the right condition and metric;
- cost: calls, tokens, seconds per document;
- re-execution stability (B8).

A protocol can then choose extractors knowing their weaknesses, and the library's claims about itself are
measured numbers.

## B12. Python interface (sketch)

```python
class Extractor(Protocol):
    spec: ExtractorSpec
    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult: ...

class RunContext:                  # given by the engine, the only way out of the extractor
    def document(self) -> anchor.Index           # the text, normalised once
    def llm(self) -> RecordingModel             # LiteLLM through gold/llm.py; every call recorded
    def agent(self, budget) -> RecordingAgent   # agentic extractors only; trajectory recorded
```

`ExtractorSpec`, `ExtractionTask`, `ExtractionResult`, `Item` and `Coverage` are pydantic models; their JSON
schemas are published with the library so results can be validated outside Python.

## B13. What exists and is reused

| Need | Existing code |
|---|---|
| Span selector, quote check, re-finding a span | `agent/anchor.py` (`Selector`, `find`, `resolve`) |
| Canonical JSON and hashes | `agent/canonical.py` |
| Hash-chained event log | `agent/broker.py` |
| Schema-constrained LLM calls, prompt hash, cache | `gold/llm.py` (`structured`, `prompt_sha256`, `cache_key`, `JsonlCache`) |
| Section-aware chunking, quote retry, per-paper coverage | `gold/chunks.py`, `gold/extract.py`, `gold/screen.py` |
| Agentic extractor | `agent/loop.py`, the sandbox, the `claim` command |
| Replay and re-execution pattern | `agent replay`, `agent reexec` |
| PROV-O export, SPARQL store | `agent/prov.py`, `scoring/store.py` |

## B14. Decisions and open questions

Decided (user, 14 Oct):

1. The same value reported twice in a paper (abstract and table) is **one item with two `value` spans**.
2. Items store **both**: `fields` hold the normalised values; the raw text is in the span.
3. Benchmark recall is **reported only**; no minimum is enforced for the thesis.

Open, for the supervisor: is an agentic extractor acceptable as one implementation behind this interface,
with its runs replayed from records and its re-execution stability reported?
