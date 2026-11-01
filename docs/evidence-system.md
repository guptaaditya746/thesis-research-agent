# Evidence-level system: interfaces and extractor contract

The file formats and the extractor interface of the evidence-level system (`evidence/`, `synth/`,
`evaluation/`). Two documents of 14 Oct 2026, merged here verbatim: **Part A** was
`docs/evidence-interfaces.md` (packages and the files between them), **Part B** was
`docs/extractor-contract.md` (the interface every extractor implements). Section numbers are kept with a
prefix, so "interfaces section 3" is now **A3** and "contract §10" is **B10**; only cross-references and
heading prefixes were changed. **Parts C–G** (17 Oct 2026) are the contracts of the realigned plan
([`STATE.md`](STATE.md) §5): C protocol version 2 (the synthesis rules in the protocol, built), D the funnel
engine, E the proposal flow (built 17 Oct; see its "As built"), F the second build (flags, knobs, variants,
intervals), G the changes to the RAG baseline, the fidelity check and the model choice. Where C changes a shape of Part A, C3 says so;
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
engine and the ground-truth generator). Existing code reused: `agent/anchor.py`, `jsonio/__init__.py`,
`agent/chain.py`, `modelcall/`, `gold/chunks.py`, `agent/prov.py`.

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

### Demo mode: real papers from arXiv

`evidence fetch --query "<words>" --max 30 --out <corpus> [--category cs.CL]` (`evidence/arxiv.py`; in the
web app the "Fetch from arXiv" button on the corpus step and the Corpora page, a job into
`$EV/corpora/arxiv-<slug>-<yyyymmdd>`) builds a corpus of **real papers**: it asks the arXiv API for the
query's papers (one request every three seconds, as arXiv's terms ask), converts each PDF to Markdown with
pymupdf4llm and writes the A1 layout the engine reads: `manifest.json` (plus title, authors, published,
url, pdf_sha256 per paper), `papers/<arxiv id>.md` and `source.json` (`kind: arxiv`, the query, when,
`ground_truth: false`, the papers skipped and why). There is no `corpus.json`, `ground_truth.json` or
`fidelity.json`.

**This is a demonstration, not a measurement.** Nobody knows the right answer for real papers, so nothing
can be scored: the app shows the corpus with a "no ground truth, demo" badge, hides Score for its runs, and
the backend refuses a score job on it ("demonstration corpus, no ground truth"). The engine runs as on any
corpus (question → cards → freeze → run → graph and answer). What a reader can still check, by hand:

1. **Grounding share.** Of the studies (or entries) the answer names, the share that rest on at least one
   evidence item whose quoted span is in the paper (the run page shows each item's span in the paper's
   text). An answer line with no item behind it is a claim the engine cannot back.
2. **A hand-checked sample of 5 papers.** Pick 5 papers at random from `manifest.json`, open each in the
   run's paper view, and check against the PDF (`url`) whether the extracted conditions, metrics and
   values are right and whether anything the question needs was missed. Write down hits, errors and misses.
   Also check the conversion: a table or formula pymupdf4llm garbled is a corpus problem, not an engine one.
3. **Re-execution stability.** `evidence reexec <run>` runs the extractors again without the cache and
   reports per call whether the items came out the same (B8). A stable run is not a correct one, but an
   unstable one should not be trusted.

Report these as a demonstration on N real papers, next to (never mixed with) the scores on the synthetic
corpora.

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

The record cache is `<cache_dir>/extractor_calls.jsonl` (`modelcall.JsonlCache`), key
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
does not count towards the label. (Changed 17 Oct: the pair keys are `treatment`/`control` and `reason` is
`{code, text}`, Part C3; every study also carries `flags` and `duplicate_of`, and the answer `counts.duplicates`,
`duplicates` and `flags`, Part F1.)

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
  over the corpus) (superseded by Part G.1, built 17 Oct: global top 8 by default); the report shows
  `answered` and `accuracy_answered` next to direction accuracy.
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
config_sha256: …                 # canonical hash of config (jsonio)
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
| R7 | Output is canonical: items sorted, JSON canonicalised (`jsonio/__init__.py`), so the same result hashes the same. |
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
  the `JsonlCache` of `modelcall/`, append-only.
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
| llm | model alias and served revision, `prompt_sha256` (instructions + output schema, `modelcall/`), temperature 0, seed, max_tokens, decoding = JSON schema, chunking settings (`gold/chunks.py`), quote-retry rule (one retry with the reason, as `gold/extract.py`) |
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
    def llm(self) -> RecordingModel             # LiteLLM through modelcall/; every call recorded
    def agent(self, budget) -> RecordingAgent   # agentic extractors only; trajectory recorded
```

`ExtractorSpec`, `ExtractionTask`, `ExtractionResult`, `Item` and `Coverage` are pydantic models; their JSON
schemas are published with the library so results can be validated outside Python.

## B13. What exists and is reused

| Need | Existing code |
|---|---|
| Span selector, quote check, re-finding a span | `agent/anchor.py` (`Selector`, `find`, `resolve`) |
| Canonical JSON and hashes | `jsonio/__init__.py` |
| Hash-chained event log | `agent/broker.py` |
| Schema-constrained LLM calls, prompt hash, cache | `modelcall/` (`structured`, `prompt_sha256`, `cache_key`, `JsonlCache`) |
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
  reason code; its evidence types (`synthesis.GAP_ROLES`, by pack role: `no_*_condition` → condition,
  `no_question_metric` → metric, `no_pair` → measurement) are the only types the next position runs,
  with the merged items of their context types as context.
- **Targeted task**: `ExtractionTask.focus: {gap: code, have: {roles: [...], metrics: [...]}, want: text}`
  (`null` on untargeted tasks; part of `task_sha256`). The LLM extractor appends a "Focus" paragraph to
  the user prompt (a targeted and an untargeted call use the same extractor id; only the task differs, so
  they are two cache entries under one id); the agentic brief adds `scope.focus` (`TEMPLATE_VERSION`
  `agentic-task-v2`). No live cache existed at the time of this change (17 Oct), so the task-hash change
  invalidated nothing. (The extractor ids themselves do change with this build, as with any change to
  `llm.py`, `llm_schema.py` or `contract.py`, which every `code_sha256` covers.)
- **Events**: `screen` (document, relevant, reason, extractor id) and `completeness` (document,
  after_position, complete, gap code, gap types); `extractor_call` unchanged. **`funnel.json`**: per
  document the ordered steps run (position, types, calls) and each decision; in `run.json.outputs`.
  `answer.json` studies gain `funnel: {screened: bool, stopped_after: position | null}`.
- **Replay and re-execution**: unchanged keys (document, type, position, extractor name); every decision
  depends only on checked results, so a `gaps` run replays from its own cache and reproduces every hash.
- **Evaluation** gains `funnel`: calls, model calls and tokens per document against the same protocol in
  `all`; the stop-position histogram; screen precision and recall against the ground truth's `relevant`.
- **Protocol**: no new keys beyond `screen`; `cascade: until_found` stays for `all`.

**As built (17 Oct), where the code deviates from the above:**

- **Escalation is per type, not per global position.** The picture above runs "position 1 for the gap
  types, then position 2". Built: after position 0 of every type, each round runs, for every gap type, the
  *next position of that type's own cascade* (`engine.Execution.funnel_loop`), until the study is complete or
  no gap type has a position left. Reason: with the shipped two-step cascades (regex, LLM), a paper whose
  baseline condition the regex misses has `condition` as the gap in round 1 and `measurement` only in round 2,
  where a global position 2 does not exist, so the LLM measurement extractor would never run and every such
  paper would end `undetermined` in `gaps` while `all` finds it. The funnel.json steps therefore carry
  `round` and `position`; a round may hold two steps when its types are at different positions.
- **`stopped_after`** is the highest cascade position run when the funnel stopped *because the study was
  complete*; `null` otherwise (`all` mode, a screened-out document, or the gap types' cascades exhausted,
  the last decision then holding the gap). A study complete after the last possible round gets a number,
  not `null`. `funnel.screened` is the screen's decision (not relevant), whatever the strategy did with it;
  funnel.json's `skipped` says whether extraction was skipped.
- **Regex screen without a hit** has no term to point at, so its negative item is anchored on the
  document's first non-empty line (the title): every item carries a checked span (R1). A term written in
  capitals only (RAG) is matched in capitals, any other term in any case. The LLM screen's fallback item
  ("unanchored") reuses the regex item's span; a screening call that returns no item (a failed model call,
  an empty document) leaves the earlier decision standing, and a cascade without any decision counts as
  relevant, so a failed check never skips a paper. The regex screen reads the whole document; the LLM
  screen reads its head only (`head_chars`, default 12000, the LLM extractors' chunk size; part of its
  config and so of its id): the screening question asks what kind of paper this is, which the title,
  abstract and introduction state, and the call's coverage names the range actually sent.
- **No re-run of a cheap position with richer context.** When an escalation adds context (the LLM finds
  the baseline condition), the funnel does not run the dependent type's position 0 again with it (the
  regex measurement extractor already ran without that condition); the next position of the dependent type
  gets the richer context instead. A re-run of position 0 is a possible later knob.
- **Events**: `screen` also carries the call ids, one status per call (`statuses`) and the deciding
  call's status; `completeness` carries `after_round` next to `after_position`; `extractor_call` gains
  `focus` (the gap code or null). funnel.json is `{strategy, documents: {id: {screen, skipped, steps,
  decisions, stopped_after}}}`; with `relink: on` (1 Nov, below) also `dangling_links`, per document (a list)
  and for the run (a count).
- **Evaluation**: `report.json.funnel` holds per-document rows, the per-document means, the stop-position
  histogram (`0`, `1`, …, `exhausted`, `skipped`) and the screen's precision and recall of the decision
  "relevant" (recall = the share of the truly relevant papers kept); the `all` run is compared with the
  `gaps` run through `evaluate compare` over both reports (one row per run), not by `evaluate score` alone.

**As built (29 Oct): GLiNER items need LLM confirmation.** In the EV3 runs, items that only the GLiNER
extractors found were almost always wrong (metrics 0 of 21, datasets 0 of 11). `Settings.confirm`
(`evidence run --confirm llm|none`, default `llm`) makes such an item *unconfirmed*: every extractor in its
`found_by` has kind `model`, and the type's cascade (as built for the run's selection) has an LLM extractor.
Once that LLM position has run, unconfirmed items are dropped from the merge and their ids listed in the merge
event's `unconfirmed` (present only when not empty); an item the LLM extractor also found is the same merged
item and stays, with both ids in `found_by`. In `all` every position of a type runs before the next type, so only
the drop applies. In `gaps` the confirmation is eager (fixed 1 Nov): when a type's position leaves unconfirmed
items and its LLM position has not run, that LLM position runs at once, in the same round (a funnel step at the LLM
position, with the type's focus unchanged), before the type is merged and before any later type gets its items as
context. So later types (a measurement linking its metric) only ever see confirmed items, and a merge never
changes the id of an item they already link to. (Built first, 29 Oct, the LLM position ran at the end of the
funnel; re-merging then gave the confirmed metric a new id and left the measurements' links dangling, so a study
the LLM agreed with became `no_pair`.) Without GLiNER, or with `regex-only` or `llm-only`, nothing changes.
run.json's settings carry `confirm` only when it is `llm`; replay of a run without the key uses `none`, so older
runs replay byte for byte. Known limit: when the LLM confirm call fails (status `error`), the type's GLiNER-only
items are still dropped.

**As built (1 Nov): links follow a re-merged item (`relink`).** Eager confirmation fixed one case of a wider bug.
In `gaps` a type escalated in a later round is merged again with its earlier results; when the later extractor
(usually the LLM) lists an item the earlier one found but quotes another span, the merged item gains that span and
its id changes (`Item.make_id` covers the span positions). Items of other types that already linked to the old id
kept the old id: the link pointed at nothing, synthesis skipped the measurement and the study could become
`no_pair`. This happened with `--confirm none` too; the EV2 `gaps` runs on `origin/results` hold such links.
`Settings.relink` (`evidence run --relink on|off`, default `on`) fixes it. `merge.merge_from` returns, next to the
merge, old id -> new id for each item of the type's previous merge whose id changed: the merge forms the earlier
results' groups first and the same way whatever follows, so each earlier item is one item now. The engine then
rewrites the links of every other type's items that point at an old id, in the checked results (so a later merge
of that type keys them by the new id) and in the merged items; an item's id does not cover its links, so no other
id changes. The merge event lists the pairs as `relinked: [[old, new], ...]` (present only when not empty).
After each document a final check lists the links that point to no item in funnel.json
(`documents.<id>.dangling_links: [[item, link name, target], ...]`) and the run's total in funnel.json and
run.json (`dangling_links`, expected 0), so a dangling link is never silent again. run.json's settings carry
`relink` only when it is `on`; replay of a run without the key uses `off`, which is the engine before 1 Nov byte
for byte (no `relinked`, no `dangling_links`). Replayed with `relink on` from their own call results, the 7 local
EV2 `cascade-gaps` runs went from 15 dangling links to 0, every study's verdict unchanged.

# Part E. Proposal flow (contract, 17 Oct 2026; our design)

The supervisor marked LLM protocol generation "with user dialogue" optional (§8). This is that dialogue
as files, so Codex, tests and later the web app drive it the same way. Directory `proposals/<slug>/`:

| Step | Command | Writes | Human |
|---|---|---|---|
| frame | `evidence propose frame --question Q --out DIR` | `frame.json`: population (which papers), treatment, control, outcomes (canonical, direction), effect labels, candidate synonyms | may edit |
| draft | `evidence propose draft DIR` | `draft.yaml` (a version-2 protocol from the frame and the example protocol); `draft.sources.json`: per field and term `frame | protocol` | — |
| critic | `evidence propose critic DIR` | `critic.json`: deterministic checks (parses; every outcome has a canonical and a direction; the regex terms cover the frame's synonyms; a screen is present; the label table is complete; every extractor is registered) and an LLM checklist (ambiguous roles, missing comparator, metric direction, scope) | reads |
| cards | `evidence propose cards DIR` | `cards.json`: the fixed choice points below, each with options, the model's default and its rationale; `decisions.yaml` prefilled with the defaults | **edits `decisions.yaml`**: per card `choice`, `reason`, `by` |
| freeze | `evidence propose freeze DIR` | `protocol.yaml` (validated as `evidence protocol check` does) and `proposal.json`: frame, sources, critic, decisions, model and prompt hashes, protocol sha256, created | — |
| amend | `evidence propose amend DIR --reason R [--before-main-run]` | `protocol.yaml` with `version + 1`; a line in `amendments.jsonl`: `{version, amends_sha256, reason, impact: [changed keys], before_main_run, at}` | gives the reason |

Choice points (fixed): 1 screening question and terms; 2 treatment and control role definitions;
3 question metrics and direction; 4 `min_effect`; 5 pairing preference; 6 label table; 7 cascade per
type and funnel strategy; 8 locate strategy. A decision without a reason is refused. Every model call
goes through `modelcall.ask` with the record cache; nothing runs a proposed protocol automatically.

**No vocabulary snapshot (removed 27 Oct).** The flow first looked each frame name up in an offline
vocabulary snapshot (`evidence/vocab/`, `evidence vocab build`) and labelled it `ontology` or `invented`.
Nothing downstream used that label, so the snapshots, the lookup, `--vocab`, `evidence vocab build` and the
`vocabulary_direction` check are gone. A frame.json written before keeps loading: its `vocabulary`, `source`
and `vocab_*` keys are dropped when it is read. The frame call still sends `Vocabulary: none.` (the text it
sent without a snapshot), so its prompt is unchanged.

**As built (17 Oct), where the code deviates from the above:** (`evidence/propose/`, tests
`evidence/tests/test_propose_*.py`)

- **`version` stays the format; a new `revision` counts amendments.** `version` is the protocol *format*
  (2 since Part C; a test asserts the shipped protocol is version 2), so `amend` does not bump it. The
  protocol gains an optional `revision` (`evidence/protocol.py`, from 1): freeze writes `revision: 1` right
  after `version`, each amendment `+ 1`. A protocol without `revision` hashes exactly as before (the field is
  left out of the sha256 when absent), so no recorded protocol hash changed. `amendments.jsonl` lines are
  `{revision, sha256, amends_sha256, reason, impact, before_main_run, at}`: `revision` where the table says
  `version`, plus `sha256` of the new revision. `evidence protocol check` prints `revision`.
- **Directory and files.** One directory per proposal (`--out DIR`; the protocol id is DIR's name as a
  slug). Beside the files of the table: `cache.jsonl` (the record cache of the model steps),
  `protocol.v<N>.yaml` (a copy of every frozen and amended revision; `amend` compares the edited
  `protocol.yaml` with the last one). Every later step records the sha256 of the inputs it read
  (`draft.sources.json.frame_sha256`, `critic.json.draft_sha256`, `cards.json.draft_sha256`), and a step
  refuses an input that changed after it was read ("run draft again"); freeze refuses a directory that is
  already frozen (changes then go through `amend`). The two files a person edits are never overwritten:
  `written.json` holds the sha256 of what `frame` and `cards` last wrote to `frame.json` and
  `decisions.yaml`, and a rerun refuses a file that differs from it, or that the step never wrote, unless
  `--force`. Refusals are `ProposalError`, exit 2 with the message (also a broken base revision, a
  non-string choice); a failed model call exits 1. The flow hashes raw bytes, so `.gitattributes` keeps
  `proposals/**` and `evidence/propose/**` LF.
- **Model calls.** frame, critic and cards make one call each through `modelcall.ask` (temperature 0,
  seed 0, thinking off), cached in `DIR/cache.jsonl` under `modelcall.cache_key({step, prompt_sha256 (the
  instructions and the output schema), model identity (modelcall.model_identity: the pinned weights of
  orch-model), input_sha256 (the user prompt), settings})`; a rerun with the same inputs makes no call.
  Each result file has `call: {step, model, prompt_sha256, cache_key, cached}`. A cached reply the step
  cannot use (a frame whose ids do not validate, a cached record that no longer fits the schema) would be
  answered from the cache forever, so the error names the cache file and key and says to run the step again
  with **`--refresh`** (frame, critic, cards): the model is asked again and the new reply is appended under
  the same key, where it wins on the next load. Default model `orch-model`
  (`--model` on the three steps), as for the extractors. Prompts `prompts/{frame,critic,cards}-v1.md`
  (read with LF line ends, so their hash is the same on every checkout).
- **The frame.** `{question, call, created, population:
  {description, screening_question, terms}, treatment, control: {role, label, definition, synonyms},
  outcomes: [{canonical, label, higher_is_better, fraction, synonyms}], effect_labels: [{value,
  direction}]}`. The population carries the screening question and the screen terms (the frame decides the
  screen; a separate list because a screen term like "retrieval" would be a wrong condition synonym), and
  each outcome says whether it is a fraction (the draft puts the [0, 1] bound on those).
  The person may edit frame.json; `draft` validates it (`Frame`, unknown keys refused).
- **The draft** (deterministic, `--template`, default the example protocol). From the template: the
  evidence types' schemas, span roles, links, context, merge keys and cascades, locate, the screen's
  extractors and `on_fail`, `min_effect`, pairing, label table and flags. From the frame: screen question
  and terms, the role enum and `compare`, the canonical enum and `metrics` (frame order is priority), the
  measurement bound on fraction outcomes, the author-claim enum and `claim_map`, the descriptions, and the
  bm25 `query` terms (the frame's names plus fixed type words per evidence type, `draft.TYPE_WORDS`). The
  regex steps get a `conditions` / `metrics` / `subject` config **only where the built-in patterns
  (`evidence/extractors/terms.py`) miss a frame name** under its role or canonical: the missing names are
  added as word-bounded patterns, and for a role or metric the built-ins do not know at all the config holds
  patterns from the frame's names only (built-in metric patterns of a canonical the frame does not name are
  dropped, since their items would fail the enum). The RAG frame therefore drafts the hand-written cascades
  without any config. `draft.sync_regex` does this from a protocol's decided roles and metrics (the
  treatment role takes the frame's treatment names, the control role the control's; a metric the frame
  lacks is named by its id with spaces, `f1`), and freeze runs it again after the decisions. `draft.sources.json`: `{frame_sha256, template: {path, sha256},
  fields: [{path, source}], terms: [{path, term, source}]}`, `source` being `frame` or `protocol`. The question itself is the input and has
  no source entry. The author-claim regex's verbs stay the built-in ones (about accuracy and hallucination).
- **The critic.** Deterministic checks as listed, defined as: `parses` (`protocol.parse`);
  `outcomes_complete` (every frame outcome is a question metric with the same direction); `terms_cover_synonyms`
  (the effective regex patterns, config else built-in, find every treatment and control name under the
  protocol's compare role and every outcome name under its canonical, using the extractors' own
  `terms.find_all`, and every treatment name holds a screen term); `screen_present` (a screen with terms);
  `label_complete` (exactly one row without `when`, the last; read from the raw YAML so it reports even when
  the protocol does not parse); `extractors_registered` (`evidence.extractors.names()`, so modules loaded by
  `evidence run --import` count as unregistered); plus two of ours: **`regex_matches_enums`** (every
  condition role and metric canonical the regex steps can emit, from their config or the built-ins, is in
  the type's enum, and every enum value but `other` has a pattern; freeze refuses a protocol that fails it). LLM checklist `ambiguous_roles`, `missing_comparator`,
  `metric_direction`, `scope`, each `{ok, message}`. `critic.json.ok` is the deterministic checks only; the
  checklist is advice and blocks nothing.
- **Cards.** `cards.yaml` holds the eight cards (ids `screen`, `roles`, `metrics`, `min_effect`,
  `pairing`, `label`, `cascade`, `locate`) with what each sets and the fixed options of the enumerable ones
  (`min_effect` 0.005/0.01/0.02, pairing table-first or order-only, label table "any evidence" or "two
  studies", locate exhaustive or bm25); `cards.py` holds per card the value's schema and how it is read from
  and written to a protocol. Options of a card: `draft` (the draft's value), the fixed options that differ
  from it (an equal one is named in the draft option's summary), for `cascade` two made from the draft
  (`gaps`: same cascades, strategy gaps; `with_agentic`: `agentic` last in every type), and `model` when the
  model proposes its own value (typed by the card's schema). The model's reply names a default per card
  with a rationale; a default naming no option falls back to `draft` and the rationale says so. **The funnel strategy is not a protocol key**
  (Part D adds none): the cascade card's `strategy` goes to `proposal.json.run_settings` as the recommended
  `evidence run --strategy`; the draft's own value is `all`, the engine's default. Rerunning `cards` refuses
  to overwrite a `decisions.yaml` a person has edited.
- **Decisions.** `decisions.yaml` is `{decisions: [{card, choice, reason, by}]}`, prefilled with the model's
  default per card, `reason: "default: <rationale>"`, `by: model`. **Freeze accepts untouched defaults** and
  records `by` per decision and `decided_by: {model: [cards], <person>: [cards]}`, so model and human
  decisions stay apart. Refused (all problems listed at once, nothing written): a missing or blank `reason`
  ("a decision without a reason is refused") or `by`; a card decided twice or not at all; an unknown card;
  **a choice that is no option of the card: refused, unless it is `custom` with a `value` in the card's
  shape** (validated by the card's schema); a `value` beside a non-custom choice; a choice other than the
  model's default still marked `by: model` (who changed it must say so); a `choice` that is not a string.
  Decisions are applied in card order; changing the metrics sets the canonical enum and keeps the
  measurement bound on the metrics still named; then **the regex patterns are made again from the decided
  roles and metrics** (`draft.sync_regex`), so dropping a metric removes its built-in patterns, and an added
  metric or a renamed role gets patterns from its names.
- **Freeze** writes `protocol.yaml` (a header comment, the applied draft with `revision: 1`) only if it
  validates as `evidence protocol check` validates, plus `protocol.v1.yaml` and `proposal.json`: `{proposal,
  question, created, protocol: {file, id, version, revision, sha256},
  models: {frame, critic, cards}, prompts: {frame, critic, cards} (prompt sha256), inputs: {frame, draft,
  critic, cards, decisions sha256, template}, run_settings, decided_by, decisions: [{card, choice, value,
  default, reason, by}], checks (the deterministic checks on the frozen protocol), frame, sources, critic}`.
  The frozen checks are recorded; only what `protocol check` refuses and a failed `regex_matches_enums`
  stop a freeze.
- **Amend** compares the parsed protocols without `revision`: dicts key by key, anything else whole (a
  list is one value), so the impact is a list of key paths such as `synthesis.min_effect` or
  `evidence_types.author_claim.extractors`, in the protocol's key order. The `revision: <n>` line is
  rewritten in place, a trailing comment kept (added after `version:` if the person removed it), so the
  person's layout and comments survive. A value on the next line (`revision:` alone), a quoted or
  flow-style `revision` key, or any edit after which the parsed revision is not the new one fall back to a
  full YAML dump of the protocol (comments lost).
  Refused: an empty reason, no change, an edit that does not validate, a directory not frozen. The
  `--protocol P` form (amend a protocol outside a proposal directory) is not built: it has no frozen base to
  compare with.
- **What test (1) compares**: the frozen protocol of the RAG question (scripted frame, critic and cards
  replies; every card's default `draft`) and `evidence/protocols/rag-factuality.yaml`, both parsed, without
  `id` and `revision`, without free text (every `description`, inside field schemas too, and the screening
  question), with the screen terms as a set and the bm25 `query` lists left out; the query tokens of the
  hand-written protocol must be a subset of the frozen one's per type. Everything else (field schemas and
  enums, bounds, cascades, locate, screen extractors, the whole synthesis block) is equal.

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
  with the same `rules.duplicate_key` (canonical metric, treatment value, control value), else `null`. The
  top-level `flags` lists and `duplicates` hold documents in manifest order, like the three groups.
- A duplicate keeps its direction (direction accuracy still scores it) but is listed under `duplicates`,
  not under `supporting`/`contradicting`/`neutral`, and the label table gets the counts without it.
- `large_effect`: `rules.large_effects` over the determined, non-duplicate studies' deltas with
  `synthesis.flags.large_effect`; `claim_disagrees`: `author_claim.agrees_with_data == false`. Neither
  changes the counts. `flags.duplicates: false` turns duplicate detection off.
- `graph.json` gains a `duplicate_of` edge; baselines report no flags.
- As built (17 Oct, ported from the ev2 bundle): the synthesis event's `custom_metadata` also carries
  `flags` (flag name -> count) next to `label` and `counts`; the PROV export is unchanged (a duplicate's
  items are among the items the answer `wasDerivedFrom`, as every study's are). `evidence protocol check P`
  validates a protocol file and prints its id, version, sha256, phases and extractors per type (exit 2 when
  it does not validate); the proposal subcommands of Part E hang beside it.

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
  studies. `corpus.json` gains `settings: {name, studies, mix, levels, duplicates, missing, outliers,
  irrelevant}` (`name` because the variant's corpus id is built from it).

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
   and per-paper stances for score C. Score C for baselines adds **completeness** and **traceability**
   next to correctness: the supervisor's three comparison criteria (§7; his criteria; the definitions that
   follow are ours). Completeness = the share of the studies with a determined true direction the answer
   gives a stance for; traceability = the share of the cited passages that overlap (share a character
   with) a ground-truth placement of any role of the study they are cited for (lenient by design), over
   all cited passages, where a citation the baseline dropped (naming no retrieved passage) counts as
   untraced; null without citations. *Built 17 Oct:* `evaluation/baselines/rag.py` (`CitedAnswer`; a
   citation must name a retrieved passage exactly, else `dropped_citations`; the mapping call reads the
   answer text and the kept citations' headers `[paper id, start-end]` only, never the passages' text, so
   it cannot read the evidence a second time), `common.map_answer` (the shared mapping,
   `MAP_INSTRUCTIONS` now naming both answer forms), `score.score_synthesis` rows carry `completeness`,
   `citations` (kept plus dropped), `traceability` (null without a `citations` list, so for the engine);
   `answer.json` of the RAG baseline: the A4 shape plus `answer_text` (the model's own answer),
   `citations`, `dropped_citations`, `retrieved`, `settings`, `model_call`, `mapping_call`,
   `mapped_answer_text`.
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
   `agent/rundir` pins, else the alias as the name with revision `unpinned`, the same the model records);
   `evidence run --model` defaults to `orch-model` while
   `engine.Settings.model` stays `None`; `modelcall.model_identity` maps `orch-model` to its pin.
