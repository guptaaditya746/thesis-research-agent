# Provenance model (adopted from PROV-AGENT and LEDGER)

Decided 10 Oct: no novelty claim on provenance. We take the record schema from PROV-AGENT and the
claim-to-evidence edges from LEDGER, and implement both in the broker's logs. Neither paper evaluates its
approach with metrics; both are qualitative case studies.

| Work | What we take | Licence |
|---|---|---|
| PROV-AGENT (Souza et al., [arXiv 2508.02866](https://arxiv.org/abs/2508.02866), IEEE e-Science 2025); code [ORNL/flowcept](https://github.com/ORNL/flowcept) | Record types and field names: `TaskObject` (`src/flowcept/commons/flowcept_dataclasses/task_object.py`), the `PROV_AGENT` subtypes (`src/flowcept/commons/vocabulary.py`), the model-call wrapper pattern (`FlowceptLLM`, `src/flowcept/instrumentation/flowcept_agent_task.py`) | MIT |
| LEDGER (Kim, Miao, Liu, [arXiv 2608.18398](https://arxiv.org/abs/2608.18398), Aug 2026) | Edge types `uses`, `produces`, `informs`, `supports`, `checked_by`; request and result of one tool call paired by `group_id`; explicit coverage records for anything not parsed | Paper CC BY 4.0, no code: mirror the schema and cite |

## Records in `events.jsonl` (one per activity, PROV-AGENT field names)

`task_id, subtype, used, generated, parent_task_id, group_id, agent_id, source_agent_id, workflow_id,
started_at, ended_at, status, custom_metadata`, plus our `step_id`, `prev_hash`, `hash`.

| `subtype` | Our event | `used` | `generated` |
|---|---|---|---|
| `ai_model_invocation` | one model call | prompt hash, model (name, revision, temperature, seed) | response hash, token usage |
| `agent_tool` | one bash command | command, files read | output hash, output file |
| `claim` | one `claim` through the broker | anchor (file, start, end, exact, prefix, suffix, file hash) | claim id |
| `spawn` | a subagent start | task text | child `agent_id` |
| `coverage` | a model output that could not be parsed, a dropped or truncated output | raw output hash | reason |

## Edges (PROV-O in the export, LEDGER names in the viewer)

| Link | LEDGER name | PROV-O |
|---|---|---|
| model call → command it emitted | `informs` | `wasInformedBy` |
| command → corpus file it read | `uses` | `used` |
| claim → step that made it | `produces` | `wasGeneratedBy` |
| anchor → claim | `supports` | `wasDerivedFrom` (claim from anchor) |
| broker check of the anchor (file hash and exact match) → claim | `checked_by` | a validation `prov:Activity` |
| subagent → parent agent | — | `actedOnBehalfOf` |
| every activity → its agent | — | `wasAssociatedWith` |
| KG edge → claim | — | `wasDerivedFrom` |

Temporal order is the hash chain; the edges above are dataflow only (LEDGER's own future-work point).

## Where we differ from LEDGER

LEDGER's links are inferred afterwards by an LLM and the paper calls the graph "an audit aid rather than a
source of truth". Ours are recorded deterministically by the broker at the moment of the claim, and each anchor
is checked against the frozen corpus (`checked_by`). That is the difference RQ1 measures.

## Queries the supervisor gets (from PROV-AGENT Q1–Q5 and the LEDGER claim walk)

1. KG edge → claim → step → exact passage.
2. Which command and which model call produced this fact.
3. All claims from one step or one subagent.
4. Claims whose anchor no longer resolves (file hash changed).
5. Answer facts with no claim behind them.

Flowcept has no PROV-O or Turtle export; we write that ourselves (`prov` or `rdflib`).
