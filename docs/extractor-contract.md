# Extractor contract (draft, 14 Oct 2026)

The supervisor's design (14 Oct) has a library of reusable evidence extractors behind a common interface,
with interchangeable implementations ("regular expressions, specialized models, LLMs, or other methods").
This page fixes that interface: what an extractor receives, what it must return, what it records, and how
a run is made to give the same data every time. It covers four kinds of extractor: **regex**, **model**,
**single-call LLM** and **agentic LLM** (our research agent as one implementation, decided 14 Oct).

## 1. Principles

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

## 2. Terms

| Term | Meaning |
|---|---|
| Evidence type | A kind of evidence the protocol asks for (`condition`, `metric`, `measurement`, `author_claim`), with a typed field schema |
| Extractor | A component that finds items of one or more evidence types in a document |
| Task | One request to an extractor: one evidence type, one document, a scope, optional context |
| Call | One execution of a task by an extractor; one provenance event |
| Item | One piece of evidence: typed fields plus one or more source spans |
| Span | A checked passage: file, offsets, exact text, prefix, suffix, file hash (`agent/anchor.py` `Selector`) |
| Coverage | What a call examined, and what it found in each part |

## 3. Identity: `ExtractorSpec`

```yaml
name: reported_result            # stable, a-z0-9_
version: 3                       # bumped by hand on any behaviour change
kind: regex | model | llm | agent
evidence_types: [measurement]
code_sha256: …                   # hash of the extractor's source files
config: { … }                    # kind-specific, section 9
config_sha256: …                 # canonical hash of config (agent/canonical.py)
determinism: exact | near_exact | variable
```

`extractor_id = name@version#sha256(code_sha256, config_sha256)[:12]`. Because the id contains both hashes, a
changed prompt or pattern cannot hit the old cache even if the version number was not bumped; the engine
warns when the hashes change but the version did not.

## 4. Input: `ExtractionTask`

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

## 5. Output: `ExtractionResult`

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

## 6. Rules

| # | Rule |
|---|---|
| R1 | Every item has at least one span; every span passes `anchor.find` against the document text whose sha256 is in the task. A failing item goes to `rejected` with its reason. |
| R2 | Fields validate against the evidence type's schema; links point to items in the task's context or in this result. |
| R3 | Spans lie inside the task's scope. |
| R4 | The extractor reads only the document, the declared context and its own configuration. |
| R5 | No randomness without a recorded seed; no clock in outputs; temperature 0 for single-call LLMs. |
| R6 | Failure is a status, not a lost call: what was found before the failure is kept (`partial`). |
| R7 | Output is canonical: items sorted, JSON canonicalised (`agent/canonical.py`), so the same result hashes the same. |
| R8 | The extractor writes no files; the engine records everything (section 7). |

## 7. Provenance: one event per call

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

## 8. Cache, replay and re-execution

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

## 9. Kind-specific configuration

| Kind | `config` holds |
|---|---|
| regex | patterns with flags, the mapping from groups to fields, value normalisers (number formats, percent → fraction) |
| model | model name and weights sha256, thresholds, input window |
| llm | model alias and served revision, `prompt_sha256` (instructions + output schema, `gold/llm.py`), temperature 0, seed, max_tokens, decoding = JSON schema, chunking settings (`gold/chunks.py`), quote-retry rule (one retry with the reason, as `gold/extract.py`) |
| agent | model alias and revision, prompt version and hash, allowed commands, the `claim` command (its accepted claims become items), budget, seed, sandbox mode; its trajectory is part of the record |

## 10. Several extractors for one evidence type

The protocol lists extractors per evidence type in order (a cascade), for example regex, then single-call
LLM, then agent for what is still missing. The engine merges their items: two items of one type with equal
normalised fields are one item that keeps all spans and a `found_by` list. The report gives each
extractor's **marginal contribution** (items only it found) and what none of them found, measured against
the synthetic ground truth.

## 11. Benchmark record per version

`extractors/<name>/<version>/benchmark.json`, made on a synthetic corpus (its id and seed recorded):

- per difficulty level (explicit, paraphrased, distributed, complex, contradictory): precision, recall, F1;
- span accuracy: the span contains the value, and the role spans point where the ground truth's rendering
  plan placed the fact;
- association accuracy: the item links to the right condition and metric;
- cost: calls, tokens, seconds per document;
- re-execution stability (section 8).

A protocol can then choose extractors knowing their weaknesses, and the library's claims about itself are
measured numbers.

## 12. Python interface (sketch)

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

## 13. What exists and is reused

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

## 14. Decisions and open questions

Decided (user, 14 Oct):

1. The same value reported twice in a paper (abstract and table) is **one item with two `value` spans**.
2. Items store **both**: `fields` hold the normalised values; the raw text is in the span.
3. Benchmark recall is **reported only**; no minimum is enforced for the thesis.

Open, for the supervisor: is an agentic extractor acceptable as one implementation behind this interface,
with its runs replayed from records and its re-execution stability reported?
