# Evidence-level system: interfaces and extractor contract

The file formats and the extractor interface of the evidence-level system (`evidence/`, `synth/`,
`evaluation/`). Two documents of 14 Oct 2026, merged here verbatim: **Part A** was
`docs/evidence-interfaces.md` (packages and the files between them), **Part B** was
`docs/extractor-contract.md` (the interface every extractor implements). Section numbers are kept with a
prefix, so "interfaces section 3" is now **A3** and "contract §10" is **B10**; only cross-references and
heading prefixes were changed. **Parts C–G** (17 Oct 2026) are the contracts of the realigned plan
([`STATE.md`](STATE.md) §5): C protocol version 2 (the synthesis rules in the protocol, built), D the funnel
engine, E the proposal flow, F the second build (flags, knobs, variants, intervals), G the changes to the
RAG baseline, the fidelity check and the model choice. Where C changes a shape of Part A, C3 says so;
Part A itself is left as written.

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

# Part C. Protocol version 2: the rules in the protocol (17 Oct 2026)

The supervisor's protocol says "how the evidence is synthesised" (§2). Until 16 Oct the engine's synthesis
was Python with the question's names inside it (`rules.METRICS`, `rules.label`); the protocol only named
them. From version 2 the protocol holds every parameter and `evidence/rules.py` holds only the machinery,
with no knowledge of the question. The benchmark generator (`synth`) reads the same block (`synth build
--protocol P`, default `evidence/protocols/rag-factuality.yaml`) and records the protocol's id and sha256
in `corpus.json` and `ground_truth.json`, so "the engine and the generator share one definition" is
literal. Our design (not the supervisor's): the choice of parameters and the decision-table form.

## C1. `synthesis`

```yaml
synthesis:
  compare: {treatment: rag, control: baseline}   # condition roles a study's pair is made of
  metrics:                                       # question metrics, priority order, with their direction
    - {canonical: factual_accuracy, higher_is_better: true}
    - {canonical: hallucination_rate, higher_is_better: false}
  min_effect: 0.01                               # |delta| below this is neutral
  pairing: {rule: same_dataset, prefer: [table_cell, document_order]}
  claim_map: {improves: supports, worsens: contradicts, no_effect: neutral}   # author claim -> direction
  label:                                         # ordered decision table over the counts
    - {when: {supporting: ">0", contradicting: ">0"}, then: mixed}
    - {when: {supporting: ">0"}, then: supported}
    - {when: {contradicting: ">0"}, then: refuted}
    - {when: {neutral: ">0"}, then: no_effect}
    - {then: insufficient}
  flags: {duplicates: true, large_effect: {factor: 3.0, min_studies: 3}}   # Part F
```

- `compare`: the two roles must differ and, when the `condition` type declares a `role` enum, be in it.
- `metrics`: canonical names in priority order (the first with a usable pair decides a study), each with
  `higher_is_better`; when the `metric` type declares a `canonical` enum, every name must be in it. The
  engine injects `question_metrics` and `compare` into every extractor's config (the regex measurement
  extractor used a hard-coded list before; regex `VERSION` is 2).
- `pairing.rule: same_dataset` (the only rule): treatment and control on the first dataset, in document
  order of the values, that has both; `prefer` orders the tie-break among several values of one
  condition, metric and dataset: `table_cell` (a Markdown table cell before prose), `document_order`.
- `claim_map`: every author-claim value (the `author_claim` type's `direction` enum, exactly) to the
  direction it asserts; `agrees_with_data` is `claim_map[claim] == direction`.
- `label`: rows in order; a row matches when every condition in `when` holds on the counts
  (`supporting`, `contradicting`, `neutral`; a condition is `<op><int>`, op in `> >= < <= ==`); the first
  matching row's `then` is the label. The last row must have no `when`; no earlier row may lack one.
  No expression language: `rules.condition_holds` is the whole parser.
- `rules.py` exports `effect(treatment, control, higher_is_better, min_effect)`, `claim_agrees(claim,
  direction, claim_map)`, `label(counts, table)`, `duplicates`, `large_effects`; the constants `METRICS`
  and `MIN_EFFECT` are gone.

## C2. `screen` (used by the funnel, Part D; parsed and recorded from version 2)

```yaml
screen:
  question: Does the paper report an experiment that compares a retrieval-augmented system with the same model answering without retrieval?
  terms: [retrieval-augmented, RAG, retrieval, closed-book, without retrieval]
  extractors: [{name: regex_screen}, {name: llm_screen}]
  on_fail: skip               # skip | extract_anyway
```

`regex_screen` answers "not relevant" when no term occurs; otherwise the next extractor answers the
question. Optional: a protocol without `screen` extracts from every document.

## C3. Changes to the shapes of Part A

- **A2 `ground_truth.json`**: `effect` is `{direction, delta, metric, treatment, control}` (measurement
  ids; were `rag`/`baseline`); top level gains `protocol: {id, sha256}`. `corpus.json` gains the same
  `protocol` and takes `question` from the protocol.
- **A4 `answer.json`**: a study's pair is `treatment: {condition, measurement, value}` and `control: {…}`
  (were `rag`/`baseline`); `reason` is `null` or `{code, text}` with codes `screened_out`,
  `no_treatment_condition`, `no_control_condition`, `no_question_metric`, `no_pair` (the text names the
  protocol's roles, e.g. "no baseline condition found").
- **`graph.json`**: the `supports`/`contradicts` edge runs from the treatment measurement to the control
  measurement (unchanged meaning, renamed source).
- **Evaluation B**: `true_pair` compares the answer's `treatment`/`control` with `effect.treatment`/
  `effect.control`; its per-study rows carry `treatment` and `control` item ids.
- **Evidence type names** stay the four of `contract.EvidenceType` (`condition`, `metric`, `measurement`,
  `author_claim`): version 2 protocols describe questions of the shape "does treatment improve a metric
  over control". Free type names are a later extension, not planned work.
- The synthesis event's `rule` is `label_table`.

# Part D. Funnel engine (contract, 17 Oct 2026; our design)

The engine of Part A runs every extractor of every cascade on every document (`all`). The funnel runs
the cheap steps first and escalates only what is still missing, per document:

```
screen ─► position 0 of every type (regex) ─► complete? ─► stop
                                                 │ no: gap types
                                                 ▼
                                   position 1 for the gap types (LLM) ─► complete? ─► stop
                                                 │ no
                                                 ▼
                                   position 2 for the gap types (agentic, targeted) ─► stop (gap recorded)
```

- **Setting** `strategy: all | gaps` (`evidence run --strategy`, default `all`; in `run.json.settings`).
- **Screen** (both strategies, when the protocol has `screen`): the screen cascade runs as extractor calls
  on a pseudo evidence type `screen` (one item: `{relevant: bool, reason: str}`, a span on the first
  matching term or the model's quote; checked, cached, replayed like any call). In `gaps` with
  `on_fail: skip`, a document screened out gets no extraction and the study `undetermined` with reason
  `screened_out` and the screen's text; in `all` the decision is recorded and extraction runs anyway, so
  screening precision and recall can be scored on the same run.
- **Completeness** = `synthesis.study()` on the document's merged items gives a direction. The gap is the
  reason code; its evidence types (`synthesis.GAP_TYPES`: `no_*_condition` → condition,
  `no_question_metric` → metric, `no_pair` → measurement) are the only types the next position runs,
  with the merged items of their context types as context.
- **Targeted task**: `ExtractionTask.focus: {gap: code, have: {roles: [...], metrics: [...]}, want: text}`
  (`null` on untargeted tasks; part of `task_sha256`). The LLM extractor appends a "Focus" paragraph to
  the user prompt (the prompt file and so the extractor id are unchanged); the agentic brief adds
  `scope.focus` (`TEMPLATE_VERSION` `agentic-task-v2`). No live cache exists before this change, so the
  task-hash change costs nothing.
- **Events**: `screen` (document, relevant, reason, extractor id) and `completeness` (document,
  after_position, complete, gap code, gap types); `extractor_call` unchanged. **`funnel.json`**: per
  document the ordered steps run (position, types, calls) and each decision; in `run.json.outputs`.
  `answer.json` studies gain `funnel: {screened: bool, stopped_after: position | null}`.
- **Replay and re-execution**: unchanged keys (document, type, position, extractor name); every decision
  depends only on checked results, so a `gaps` run replays from its own cache and reproduces every hash.
- **Evaluation** gains `funnel`: calls, model calls and tokens per document against the same protocol in
  `all`; the stop-position histogram; screen precision and recall against the ground truth's `relevant`.
- **Protocol**: no new keys beyond `screen`; `cascade: until_found` stays for `all`.

# Part E. Proposal flow (contract, 17 Oct 2026; our design)

The supervisor marked LLM protocol generation "with user dialogue" optional (§8). This is that dialogue
as files, so Codex, tests and later the web app drive it the same way. Directory `proposals/<slug>/`:

| Step | Command | Writes | Human |
|---|---|---|---|
| frame | `evidence propose frame --question Q [--vocab V] --out DIR` | `frame.json`: population (which papers), treatment, control, outcomes (canonical, direction), effect labels, candidate synonyms; every entry `source: ontology | invented` | may edit |
| draft | `evidence propose draft DIR` | `draft.yaml` (a version-2 protocol from the frame and the example protocol); `draft.sources.json`: per field and term `ontology | protocol | invented`, with the vocabulary entry id | — |
| critic | `evidence propose critic DIR` | `critic.json`: deterministic checks (parses; every outcome has a canonical and a direction; the regex terms cover the frame's synonyms; a screen is present; the label table is complete; every extractor is registered) and an LLM checklist (ambiguous roles, missing comparator, metric direction, scope) | reads |
| cards | `evidence propose cards DIR` | `cards.json`: the fixed choice points below, each with options, the model's default, its rationale and the vocabulary evidence; `decisions.yaml` prefilled with the defaults | **edits `decisions.yaml`**: per card `choice`, `reason`, `by` |
| freeze | `evidence propose freeze DIR` | `protocol.yaml` (validated as `evidence protocol check` does) and `proposal.json`: frame, sources, critic, decisions, vocabulary `{name, sha256}`, model and prompt hashes, protocol sha256, created | — |
| amend | `evidence propose amend DIR --reason R [--before-main-run]` | `protocol.yaml` with `version + 1`; a line in `amendments.jsonl`: `{version, amends_sha256, reason, impact: [changed keys], before_main_run, at}` | gives the reason |

Choice points (fixed): 1 screening question and terms; 2 treatment and control role definitions;
3 question metrics and direction; 4 `min_effect`; 5 pairing preference; 6 label table; 7 cascade per
type and funnel strategy; 8 locate strategy. A decision without a reason is refused. Every model call
goes through `gold/llm.structured` with the record cache; nothing runs a proposed protocol automatically.

**Vocabulary snapshot** `evidence/vocab/<name>.json`: `{name, sha256, sources: [{name, version, url}],
terms: [{id, label, synonyms, kind: metric | condition | method, source, higher_is_better?}]}`, built
offline by `evidence vocab build` from local downloads (CS-KG 2.0 terms and synonyms, Papers with Code
metric names, ML-Schema's measurement shape, EXPO's roles; DBLP only for metadata); a small hand-checked
snapshot for the RAG question is committed. The flow runs without one (sources are then `protocol` or
`invented`). The evidence graph does not use it (decided 16 Oct).

# Part F. Second build (ev2): flags, benchmark knobs, counterfactual variants, intervals, benchmark records

The contract of 15 Oct (bundle `../thesis-ev2-wip.bundle`, df60939 §7), adapted to version 2. Shared
definitions are `rules.duplicates`, `rules.large_effects` and `rules.FLAGS`, parameters from
`synthesis.flags`. The hard rule of Part A stands.

## F1. Flags (engine, `answer.json`)

The supervisor's synthesis step names three flags: an author claim that disagrees with its own computed
label, duplicated studies, unusually large effects. The engine reports them; only duplicates change the
counts.

```json
{
  "counts": {"supporting": 3, "contradicting": 1, "neutral": 0, "undetermined": 1, "duplicates": 1},
  "studies": [{"document": "S021", "direction": "supports", "flags": ["duplicate"], "duplicate_of": "S003"}],
  "duplicates": ["S021"],
  "flags": {"claim_disagrees": ["S007"], "duplicate": ["S021"], "large_effect": ["S012"]}
}
```

- `flags` per study: sorted, from `rules.FLAGS`; `duplicate_of` is the earlier document (manifest order)
  with the same `rules.duplicate_key` (canonical metric, treatment value, control value), else `null`.
- A duplicate keeps its direction (direction accuracy still scores it) but is listed under `duplicates`,
  not under `supporting`/`contradicting`/`neutral`, and the label table gets the counts without it.
- `large_effect`: `rules.large_effects` over the determined, non-duplicate studies' deltas with
  `synthesis.flags.large_effect`; `claim_disagrees`: `author_claim.agrees_with_data == false`. Neither
  changes the counts. `flags.duplicates: false` turns duplicate detection off.
- `graph.json` gains a `duplicate_of` edge; baselines report no flags.

## F2. Benchmark knobs (generator)

`synth build` gains `--duplicates N --missing N --outliers N --irrelevant N` (default 0; the plain build
stays byte for byte what it was: the extra draws come from their own `random.Random` streams).

| Knob | Papers it adds or changes | Ground truth |
|---|---|---|
| `--duplicates N` | N extra papers (`S021`, …), each a second report of an existing study: same conditions, metrics, datasets and values (fact ids under the new study id), a different title and filler, at the original's level | study `duplicate_of`, `flags: ["duplicate"]`; effect as the original's; left out of `answer` counts, listed in `answer.duplicates` |
| `--missing N` | N studies lack the control (alternately the treatment) measurement on the question metric: the paper never states it (a dash in a complex table) | `missing: "control" | "treatment"`, `effect: {direction: "undetermined", delta: null, …, reason: "missing_control" | "missing_treatment"}`; in `answer.undetermined`, not counted |
| `--outliers N` | N supporting studies get an effect of 0.30–0.45 | `flags: ["large_effect"]`; counted |
| `--irrelevant N` | N papers with no treatment/control experiment (a survey or a paper on another topic, from the vocabulary) | study `relevant: false`, no conditions/metrics/measurements/claim, expected `screened_out`; in `answer.undetermined`, not counted |

- Every study has `relevant` (default `true`), `flags` (sorted, possibly empty), `duplicate_of` and
  `missing` (`null` by default); contradictory-level papers carry `flags: ["claim_disagrees"]`.
- The generator asserts that `rules.duplicates` and `rules.large_effects` on its own studies give exactly
  the planted ones, and keeps the (treatment, control) pairs of distinct studies apart on both datasets.
- `answer` gains `undetermined`, `duplicates` and `flags`; `label` is the label table over the counted
  studies. `corpus.json` gains `settings: {studies, mix, levels, duplicates, missing, outliers, irrelevant}`.

## F3. Counterfactual variants (generator, `variant.json`)

The supervisor's controlled variant: change one study's result and regenerate only that paper, so the
expected answer shifts in a known way.

```
uv run synth variant --corpus corpora/rag-s1-mixed --study S003 --direction contradicts [--out DIR] [renderer options]
```

Writes `<corpus>-cf-<study>-<direction>` (or `--out`): every other paper byte for byte the base corpus's,
the chosen paper re-rendered at its level from a counterfactual study with the new effect direction on
both datasets (same ids, names, datasets, distractors; the pair redrawn from
`random.Random(f"synth:{seed}:{study}:variant:{direction}")`; the claim follows the new effect except a
contradictory-level paper keeps a false claim), fidelity-checked as in `build` (a failure is an error).
Flags re-applied to the whole set. Files as in a build plus `variant.json`:
`{base_corpus_id, corpus_id, study, paper, from, to, changed: [{measurement, from, to}], expected:
{before: {label, counts}, after: {label, counts}, label_changes}}`; `corpus.json` gains
`variant: {base_corpus_id, study, from, to}`.

## F4. Evaluation additions

- **Intervals**: `report.json` gains `intervals`, 95 % BCa bootstrap (scipy, 2,000 resamples, seed 0,
  resampling papers) for extraction F1 per evidence type, direction accuracy per system, and the paired
  difference in direction accuracy between the engine and each baseline; a degenerate sample gives the
  point value with `null` bounds. `report.md` and `compare.md` show `0.812 [0.74, 0.88]`.
- **Expected `undetermined`**: a study whose true effect is `undetermined` (missing information) or that
  is `relevant: false` is right when the system says `undetermined`; `answered` and `accuracy_answered`
  are over the studies with a determined expected direction.
- **Flags (C)**: per flag, precision and recall against the ground truth's flags; `counts_correct`;
  `duplicates_correct`. A system without `flags` gets `null`.
- **`evaluate shift --base REPORT --variant REPORT --variant-json variant.json --out DIR`**: per system the
  changed study's direction before and after against `from`/`to`, the label before and after against
  `expected`, and `shifted_as_expected`; `shift.json`, `shift.md`.
- **`evaluate benchmark REPORT [REPORT …] --out DIR`**: the record of B11 per extractor id: per evidence
  type and level precision, recall, F1 of the items it found (`found_by`), span accuracy, cost per call,
  re-execution stability where present; `DIR/<extractor_id>/benchmark.json` and one `benchmark.md`.

The §7.5 LLM proposer of 15 Oct is dropped: Part E replaces it.

# Part G. Changes to what Part A6 describes as built (decided 16 Oct, built in step 2 of the plan)

1. **RAG baseline** = plain retrieve-then-answer: default `--retrieval global --k 8` (top passages over
   the whole corpus; `per_paper` stays as the option "every paper seen"); the prompt asks for an answer
   with citations only ("Answer the question using only the passages below. Say what the evidence shows
   and cite the passages you rely on as [paper id, start-end]."), output `{answer_text, citations}`; a
   separate mapping call (the agent baseline's `MAP_INSTRUCTIONS`, shared) turns the answer into a label
   and per-paper stances for score C. Score C for baselines adds **completeness** (determined true studies
   the answer gives a stance for) and **traceability** (cited passages that overlap a ground-truth
   placement of the study they are cited for, over cited passages), the supervisor's three comparison
   criteria (§7). *Built 17 Oct:* `evaluation/baselines/rag.py` (`CitedAnswer`; a citation must name a
   retrieved passage exactly, else `dropped_citations`; the mapping call reads the answer text and the
   cited passages), `common.map_answer` (the shared mapping, `MAP_INSTRUCTIONS` now naming both answer
   forms), `score.score_synthesis` rows carry `completeness`, `citations`, `traceability` (null without a
   `citations` list, so for the engine); `answer.json` of the RAG baseline: the A4 shape plus `answer_text`
   (the model's own answer), `citations`, `dropped_citations`, `retrieved`, `settings`, `model_call`,
   `mapping_call`, `mapped_answer_text`.
2. **Fidelity** fails a paper that adds content: `added_numbers` (a number outside the value placements,
   the decoys and an explicit allowlist: the plan's dataset sizes, `Table n`/`Section n`, list markers,
   `A1`-style codes), `added_claims` (a sentence matching the question's claim patterns outside the claim
   placement), `blind_extra` (with `--verify-model`, a measurement the blind reader returns that is not
   planned). The writer prompt's rules 3 and 4 are thereby enforced.
3. **One model**: `orch-model` for every extractor and both baselines (`AgentSettings.model`; `evidence run
   --model` default `orch-model`; `llm` extractors' default `orch-model`; `evaluate … --model` reaches the
   agent baseline's agent); the synthetic papers are written by `sub-model-1` so writer and reader are
   different weights. The runbook's model table and rules follow. *Built 17 Oct:* `AgentSettings.model`
   (default `orch-model`; the runner builds the agent's `OrchestratorModel` on it, `runner.default_model`),
   recorded in the agentic extractor's config as `{alias, name, revision}` (the pinned weights of an alias
   `agent/rundir` pins, else the alias alone); `evidence run --model` defaults to `orch-model` while
   `engine.Settings.model` stays `None`; `gold/llm.model_identity` maps `orch-model` to its pin.
